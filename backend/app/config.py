"""Validated runtime configuration. Secrets are read from the environment only."""

import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .governor import ChannelGovernor

ROOT = Path(__file__).resolve().parents[1]


Runtime = Literal[
    "llama_cpp",
    "kokoro",
    "qwen_tts",
    "whisper",
    "ctc_aligner",
    "sentence_transformers",
    "diffusers",
    "diffusers_gguf",
]

# Runtimes that may offload to Apple Metal (llama.cpp) or torch MPS (Kokoro, Qwen3-TTS).
METAL_RUNTIMES = {"llama_cpp", "kokoro", "qwen_tts"}
CUDA_ONLY_RUNTIMES = {"diffusers", "diffusers_gguf"}

# ModelSpec fields the dashboard may override per role. runtime, extra_repos, and
# stage routes stay in the hardware profile so validate_routes keeps its meaning.
OVERRIDABLE_FIELDS = frozenset(
    {
        "repo_id",
        "revision",
        "filename",
        "files",
        "device",
        "gpu_layers",
        "context_size",
        "max_tokens",
        "voice",
        "speed",
        "steps",
    }
)

# Runtime → optional dependency group in pyproject.toml. The only install the
# API will ever run is `uv sync --extra <one of these values>`.
RUNTIME_EXTRAS: dict[str, str] = {
    "llama_cpp": "llm",
    "kokoro": "audio",
    "qwen_tts": "audio",
    "whisper": "audio",
    "ctc_aligner": "audio",
    "sentence_transformers": "embeddings",
    "diffusers": "images",
    "diffusers_gguf": "images",
}


def _check_relative(names):
    for name in names:
        if Path(name).is_absolute() or ".." in Path(name).parts:
            raise ValueError("Model file patterns must be relative paths")


class ExtraRepo(BaseModel):
    """Companion snapshot pinned in the same manifest (e.g. a GGUF text encoder)."""

    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=40, pattern=r"^[a-z][a-z0-9_]*$")
    repo_id: str
    revision: str = "main"
    files: list[str] = Field(min_length=1)
    filename: str | None = None

    @model_validator(mode="after")
    def validate_files(self):
        _check_relative(self.files + ([self.filename] if self.filename else []))
        return self


class ModelSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    runtime: Runtime
    repo_id: str
    revision: str = "main"
    files: list[str] = Field(min_length=1)
    filename: str | None = None
    extra_repos: list[ExtraRepo] = Field(default_factory=list)
    device: Literal["cpu", "cuda", "metal"] = "cpu"
    context_size: int = Field(default=8192, ge=512, le=32768)
    max_tokens: int = Field(default=2048, ge=64, le=8192)
    gpu_layers: int = Field(default=0, ge=-1)
    # Appended to the system prompt for GGUF chat models (Qwen3/SmolLM3 soft switch).
    think_toggle: str | None = "/no_think"
    priority: int = 10
    timeout_seconds: float = Field(default=600, gt=0, le=7200)
    voice: str = "af_heart"
    speaker: str = "Ryan"
    speed: float = Field(default=1, ge=0.5, le=2)
    steps: int = Field(default=4, ge=1, le=50)

    @model_validator(mode="after")
    def validate_files(self):
        _check_relative(self.files + ([self.filename] if self.filename else []))
        if len({extra.name for extra in self.extra_repos}) != len(self.extra_repos):
            raise ValueError("extra_repos names must be unique")
        if (
            self.runtime in ("llama_cpp", "kokoro", "diffusers_gguf")
            and not self.filename
        ):
            raise ValueError(
                "GGUF, Kokoro, and GGUF diffusion models require an explicit weight filename"
            )
        if self.runtime == "diffusers_gguf":
            names = {extra.name for extra in self.extra_repos}
            if not {"base", "text_encoder"}.issubset(names):
                raise ValueError(
                    "diffusers_gguf requires extra_repos named base and text_encoder"
                )
        if self.runtime == "sentence_transformers" and self.device != "cpu":
            raise ValueError("The embedding runtime uses CPU to preserve GPU capacity")
        if self.device == "metal" and self.runtime not in METAL_RUNTIMES:
            raise ValueError(f"{self.runtime} does not support the metal device")
        if self.runtime in CUDA_ONLY_RUNTIMES and self.device != "cuda":
            raise ValueError(f"{self.runtime} requires device: cuda")
        return self


class Governor(BaseModel):
    # Worker retries per stage for transient model failures.
    max_attempts: int = Field(default=3, ge=1, le=5)
    # Critic → rewrite rounds before ReviewRequired.
    critique_rounds: int = Field(default=3, ge=1, le=5)
    critic_temperature: float = Field(default=0.3, ge=0, le=1.5)
    min_script_score: float = Field(default=8.5, ge=0, le=10)
    min_research_confidence: float = Field(default=0.9, ge=0, le=1)
    max_similarity: float = Field(default=0.9, ge=0, le=1)
    max_images: int = Field(default=3, ge=0, le=20)
    # Alignment fails closed when the narration audio drifts from the script.
    min_narration_fidelity: float = Field(default=0.85, ge=0, le=1)


class ModelConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    models: dict[str, ModelSpec]
    routes: dict[str, str]
    governor: Governor = Field(default_factory=Governor)
    images_enabled: bool = False

    @model_validator(mode="after")
    def validate_routes(self):
        required = {
            "research": {"llama_cpp"},
            "verification": {"llama_cpp"},
            "outline": {"llama_cpp"},
            "script": {"llama_cpp"},
            "critique": {"llama_cpp"},
            "storyboard": {"llama_cpp"},
            "metadata": {"llama_cpp"},
            "narration": {"kokoro", "qwen_tts"},
            "alignment": {"whisper", "ctc_aligner"},
            "similarity": {"sentence_transformers"},
        }
        if self.images_enabled:
            required["assets"] = {"diffusers", "diffusers_gguf"}
        for stage, runtimes in required.items():
            model = self.models.get(self.routes.get(stage, ""))
            if model is None or model.runtime not in runtimes:
                raise ValueError(
                    f"{stage} requires a configured {' or '.join(sorted(runtimes))} model route"
                )
        return self


def _merge(base: dict, overlay: dict) -> dict:
    merged = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def read_overlay(overlay_path: Path) -> dict:
    """Operator overrides saved by the dashboard: {"models": {role: {field: value}}}."""
    if not overlay_path.exists():
        return {}
    data = yaml.safe_load(overlay_path.read_text()) or {}
    if not isinstance(data, dict) or not isinstance(data.get("models", {}), dict):
        raise TypeError(f"{overlay_path} must be a mapping with a models section")
    return data


def _check_overlay(overlay: dict) -> None:
    for role, fields in overlay.get("models", {}).items():
        if not isinstance(fields, dict):
            raise TypeError(f"Override for {role} must be a mapping")
        unknown = set(fields) - OVERRIDABLE_FIELDS
        if unknown:
            raise ValueError(
                f"Override for {role} touches non-overridable fields: {', '.join(sorted(unknown))}"
            )


def load_model_config(path: Path, overlay_path: Path) -> tuple[ModelConfig, dict]:
    """Validate the profile at ``path`` merged with the overlay; return (config, overlay)."""
    base = yaml.safe_load(path.read_text())
    overlay = read_overlay(overlay_path)
    _check_overlay(overlay)
    return ModelConfig.model_validate(_merge(base, overlay)), overlay


def load_channel_governor(env_name: str) -> ChannelGovernor:
    data = yaml.safe_load((ROOT / "config/default.yaml").read_text())
    overlay = ROOT / "config" / f"{env_name}.yaml"
    if overlay.exists() and env_name != "default":
        data = _merge(data, yaml.safe_load(overlay.read_text()) or {})
    return ChannelGovernor.model_validate(data)


class Settings:
    def __init__(self):
        legacy = os.getenv("DATABASE_PATH", str(ROOT / "data/jobs.sqlite3"))
        self.database_url = os.getenv(
            "DATABASE_URL", f"sqlite:///{Path(legacy).resolve()}"
        )
        if self.database_url.startswith("postgresql://"):
            self.database_url = self.database_url.replace(
                "postgresql://", "postgresql+psycopg://", 1
            )
        self.mode = os.getenv("PIPELINE_MODE", "mock")
        if self.mode not in ("mock", "local"):
            raise ValueError("PIPELINE_MODE must be mock or local")
        self.app_env = os.getenv("APP_ENV", "development")
        self.channel_governor = load_channel_governor(self.app_env)
        self.model_config_path = Path(
            os.getenv("MODEL_CONFIG", str(ROOT / "config/models.yaml"))
        )
        self.model_overlay_path = Path(
            os.getenv("MODEL_OVERLAY", str(ROOT / "data/models.local.yaml"))
        )
        self.models, self.model_overrides = load_model_config(
            self.model_config_path, self.model_overlay_path
        )
        self.cache_dir = Path(
            os.getenv("MODEL_CACHE_DIR", str(ROOT / "data/models"))
        ).resolve()
        self.artifact_dir = Path(
            os.getenv("ARTIFACT_DIR", str(ROOT / "data/artifacts"))
        ).resolve()
        self.run_worker = os.getenv("RUN_WORKER", "true").lower() == "true"
        self.origins = os.getenv(
            "CORS_ORIGINS", "http://localhost:3091,http://127.0.0.1:3091"
        ).split(",")
        self.redis_url = os.getenv("REDIS_URL") or None
        self.temporal_target = os.getenv("TEMPORAL_TARGET") or None
        self.series_asset_max_bytes = int(
            os.getenv("SERIES_ASSET_MAX_BYTES", str(50 * 1024 * 1024))
        )
        if self.series_asset_max_bytes <= 0:
            raise ValueError("SERIES_ASSET_MAX_BYTES must be positive")
        self.storage_backend = os.getenv("STORAGE_BACKEND", "local")
        if self.storage_backend not in ("local", "s3"):
            raise ValueError("STORAGE_BACKEND must be local or s3")
        self.s3_endpoint = os.getenv("S3_ENDPOINT", "http://127.0.0.1:9000")
        self.s3_access_key = os.getenv("S3_ACCESS_KEY", "minioadmin")
        self.s3_secret_key = os.getenv("S3_SECRET_KEY", "minioadmin")
        self.s3_bucket = os.getenv("S3_BUCKET", "video-artifacts")
        self.s3_region = os.getenv("S3_REGION", "us-east-1")
        log_format = os.getenv(
            "LOG_FORMAT", self.channel_governor.observability.log_format
        )
        if log_format not in ("json", "text"):
            raise ValueError("LOG_FORMAT must be json or text")
        self.log_format = log_format

    def override_for(self, role: str) -> dict:
        return dict(self.model_overrides.get("models", {}).get(role, {}))

    def _apply_overlay(self, overlay: dict) -> ModelConfig:
        """Validate the profile merged with ``overlay`` before anything is written."""
        _check_overlay(overlay)
        base = yaml.safe_load(self.model_config_path.read_text())
        config = ModelConfig.model_validate(_merge(base, overlay))
        path = self.model_overlay_path
        if overlay.get("models"):
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(".tmp")
            temporary.write_text(yaml.safe_dump(overlay, sort_keys=True))
            temporary.replace(path)
        elif path.exists():
            path.unlink()
        self.models, self.model_overrides = config, overlay
        return config

    def save_override(self, role: str, fields: dict) -> ModelConfig:
        """Merge ``fields`` into the role's overlay entry; raises ValueError when invalid."""
        if role not in self.models.models:
            raise KeyError(role)
        overlay = {
            **self.model_overrides,
            "models": {
                **self.model_overrides.get("models", {}),
                role: {**self.override_for(role), **fields},
            },
        }
        return self._apply_overlay(overlay)

    def reset_override(self, role: str) -> ModelConfig:
        models = {
            key: value
            for key, value in self.model_overrides.get("models", {}).items()
            if key != role
        }
        return self._apply_overlay({**self.model_overrides, "models": models})
