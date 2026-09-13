import asyncio
import importlib.util
import logging
from contextlib import asynccontextmanager, nullcontext, suppress
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .artifacts import Artifacts
from .config import CUDA_ONLY_RUNTIMES, OVERRIDABLE_FIELDS, RUNTIME_EXTRAS, Settings
from .infra import RedisGateway
from .local_provider import IntegrationUnavailable, LocalProvider, ReviewRequired
from .models.hub import ModelHub, ModelNotReady
from .models.setup import SetupBusy, SetupManager
from .observability import configure_logging, render_metrics
from .orchestrator.client import check_temporal
from .providers import MockProvider, Provider
from .schemas import Source
from .storage import build_object_store
from .store import Store

logger = logging.getLogger(__name__)

CONFIG_CHANGED = (
    "Model configuration changed since this job was created. "
    "Restart the pipeline to run from scratch with the current models."
)

# Runtime name → importable module used to report "runtime installed".
RUNTIME_MODULES = {
    "llama_cpp": "llama_cpp",
    "kokoro": "kokoro",
    "qwen_tts": "qwen_tts",
    "whisper": "faster_whisper",
    "ctc_aligner": "ctc_forced_aligner",
    "sentence_transformers": "sentence_transformers",
    "diffusers": "diffusers",
    "diffusers_gguf": "diffusers",
}


async def _probe(operation):
    try:
        return await operation()
    except (OSError, TimeoutError, RuntimeError, ValueError) as exc:
        logger.warning("health probe failed: %s", exc)
        return "error"


async def _probe_database(store):
    try:
        with store.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return "ok"
    except (OSError, TimeoutError, RuntimeError, ValueError, SQLAlchemyError) as exc:
        logger.warning("database probe failed: %s", exc)
        return "error"


class JobInput(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    brief: str = Field(default="", max_length=5000)
    sources: list[Source] = Field(default_factory=list, max_length=10)

    @field_validator("title")
    @classmethod
    def clean_title(cls, value):
        if not value.strip():
            raise ValueError("Title must not be blank")
        return value.strip()

    @field_validator("sources")
    @classmethod
    def unique_sources(cls, sources):
        if len({source.id for source in sources}) != len(sources):
            raise ValueError("Source IDs must be unique")
        return sources


def _explain(exc: Exception) -> str:
    """Compact pydantic errors to `models.role.field: message` for the dashboard."""
    if not isinstance(exc, ValidationError):
        return str(exc)
    parts = []
    for error in exc.errors(include_url=False, include_input=False):
        location = ".".join(str(item) for item in error["loc"])
        message = error["msg"].removeprefix("Value error, ")
        parts.append(f"{location}: {message}" if location else message)
    return "; ".join(parts)


class ModelOverride(BaseModel):
    """Per-role override saved to the overlay file. Unset fields are left untouched."""

    model_config = ConfigDict(extra="forbid")
    repo_id: str | None = Field(default=None, min_length=1)
    revision: str | None = Field(default=None, min_length=1)
    filename: str | None = None
    files: list[str] | None = Field(default=None, min_length=1)
    device: Literal["cpu", "cuda", "metal"] | None = None
    gpu_layers: int | None = None
    context_size: int | None = None
    max_tokens: int | None = None
    voice: str | None = None
    speed: float | None = None
    steps: int | None = None


def create_app(
    db_path: str | None = None, provider: Provider | None = None, settings=None
):
    settings = settings or Settings()
    configure_logging(settings.log_format)
    store = Store(db_path or settings.database_url)
    objects = build_object_store(settings)
    redis = RedisGateway(settings.redis_url)
    provider = provider or (
        LocalProvider(settings, store) if settings.mode == "local" else MockProvider()
    )
    hub = ModelHub(settings.cache_dir)
    setup = SetupManager(hub)
    artifacts = Artifacts(settings.artifact_dir)

    async def process(job):
        try:
            if job.get("mode", "mock") != settings.mode:
                raise ReviewRequired(
                    "This job was created in a different provider mode. Restore its mode or create a new draft."
                )
            if settings.mode == "local" and job.get("config_hash") != getattr(
                provider, "config_hash", None
            ):
                raise ReviewRequired(CONFIG_CHANGED)
            for stage in job["stages"]:
                if settings.mode == "local" and job.get("config_hash") != getattr(
                    provider, "config_hash", None
                ):
                    raise ReviewRequired(CONFIG_CHANGED)
                if stage["status"] == "completed":
                    continue
                if stage["name"] == "upload" and not job["approved_at"]:
                    job["status"] = "awaiting_approval"
                    store.save(job)
                    return
                # Mock failures remain manual; real transient model failures have bounded retries.
                attempts = (
                    settings.models.governor.max_attempts
                    if settings.mode == "local"
                    else 1
                )
                for index in range(attempts):
                    stage["status"] = "running"
                    store.save(job)
                    attempt_id = store.start_attempt(job["id"], stage["name"])
                    try:
                        stage["output"] = await provider.execute(stage["name"], job)
                        store.finish_attempt(
                            attempt_id,
                            "completed",
                            provenance=stage["output"].get("provenance", {}),
                        )
                        stage["status"] = "completed"
                        store.save(job)
                        break
                    except asyncio.CancelledError:
                        store.finish_attempt(
                            attempt_id, "interrupted", error="Worker stopped"
                        )
                        raise
                    except Exception as exc:
                        store.finish_attempt(
                            attempt_id,
                            "failed",
                            error=str(exc),
                            provenance=getattr(exc, "details", {}),
                        )
                        if (
                            isinstance(
                                exc,
                                (ReviewRequired, IntegrationUnavailable, ModelNotReady),
                            )
                            or index + 1 == attempts
                        ):
                            raise
                        await asyncio.sleep(min(2**index, 8))
            job["status"] = "completed"
            store.save(job)
        except (Exception, asyncio.CancelledError) as exc:
            job["status"] = "failed"
            job["error"] = str(exc) or "Worker stopped; retry to resume"
            for stage in job["stages"]:
                if stage["status"] == "running":
                    stage["status"] = "failed"
            store.save(job)
            if isinstance(exc, asyncio.CancelledError):
                raise

    async def worker():
        while True:
            job = store.claim()
            if job:
                await process(job)
            else:
                await asyncio.sleep(0.25)

    @asynccontextmanager
    async def lifespan(app):
        with store.worker_lock() if settings.run_worker else nullcontext():
            task = None
            if settings.run_worker:
                store.recover()
                task = asyncio.create_task(worker())
            app.state.worker_task = task
            try:
                yield
            finally:
                if task:
                    task.cancel()
                    with suppress(asyncio.CancelledError):
                        await task
                store.engine.dispose()

    app = FastAPI(title="Video Orchestrator", lifespan=lifespan)
    app.state.store = store
    app.state.hub = hub
    app.state.setup = setup
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.origins,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type"],
    )

    def get_job(job_id):
        job = store.get(job_id)
        if not job:
            raise HTTPException(404, "Video job not found")
        return job

    @app.get("/api/health")
    async def health():
        task = getattr(app.state, "worker_task", None)
        worker = (
            "ok"
            if not settings.run_worker or (task and not task.done())
            else "degraded"
        )
        dependencies = {
            "worker": worker,
            "database": await _probe_database(store),
            "storage": await _probe(objects.ping),
            "redis": await _probe(redis.ping),
            "temporal": await _probe(lambda: check_temporal(settings.temporal_target)),
        }
        required = ["worker", "database", "storage"]
        status = (
            "ok"
            if all(dependencies[name] == "ok" for name in required)
            and all(
                value in {"ok", "disabled"}
                for key, value in dependencies.items()
                if key not in required
            )
            else "degraded"
        )
        return {
            "status": status,
            "provider": settings.mode,
            "database": store.engine.dialect.name,
            "approval_required": not settings.channel_governor.may_publish_without_human(),
            "worker_enabled": settings.run_worker,
            "dependencies": dependencies,
        }

    @app.get("/metrics")
    async def metrics():
        body, media = render_metrics()
        return Response(content=body, media_type=media)

    @app.get("/api/system")
    async def system():
        governor = settings.channel_governor
        return {
            "env": settings.app_env,
            "channel": governor.channel.model_dump(),
            "automation": governor.automation.model_dump(),
            "content": governor.content.model_dump(),
            "budgets": governor.budgets.model_dump(),
            "external_llm": {
                **governor.external_llm.model_dump(exclude={"provider"}),
                "provider": governor.external_llm.provider
                if governor.external_llm.enabled
                else None,
            },
            "human_required": governor.human_required,
            "storage_backend": settings.storage_backend,
        }

    def models_payload():
        importlib.invalidate_caches()
        result = []
        for role, spec in settings.models.models.items():
            try:
                manifest = hub.resolve(spec)
                cached, revision = True, manifest["revision"]
            except (ModelNotReady, OSError, ValueError, KeyError):
                cached, revision = False, None
            extra = RUNTIME_EXTRAS[spec.runtime]
            result.append(
                {
                    "role": role,
                    "repo_id": spec.repo_id,
                    "runtime": spec.runtime,
                    "device": spec.device,
                    "cached": cached,
                    "revision": revision,
                    "runtime_installed": importlib.util.find_spec(
                        RUNTIME_MODULES[spec.runtime]
                    )
                    is not None,
                    "stages": [
                        stage
                        for stage, selected in settings.models.routes.items()
                        if selected == role
                    ],
                    "enabled": spec.runtime not in CUDA_ONLY_RUNTIMES
                    or settings.models.images_enabled,
                    "extra": extra,
                    "install_command": f"uv sync --extra {extra}",
                    "overridden": bool(settings.override_for(role)),
                    "spec": spec.model_dump(include=set(OVERRIDABLE_FIELDS)),
                    "setup": {
                        "download": setup.status(f"download:{role}"),
                        "install": setup.status(f"install:{extra}"),
                    },
                }
            )
        runner = getattr(provider, "runner", None)
        return {
            "mode": settings.mode,
            "models": result,
            "gpu": runner.gpu.status()
            if runner and hasattr(runner, "gpu")
            else {"active": None, "queued": []},
            "images_enabled": settings.models.images_enabled,
            "setup_running": setup.any_running(),
            "overlay_path": str(settings.model_overlay_path),
        }

    def get_spec(role):
        spec = settings.models.models.get(role)
        if spec is None:
            raise HTTPException(404, "Unknown model role")
        return spec

    def reject_if_downloading(role):
        if setup.is_running(f"download:{role}"):
            raise HTTPException(
                409, f"Wait for the {role} download to finish before changing it"
            )

    @app.get("/api/models")
    async def models():
        return models_payload()

    @app.post("/api/models/{role}/download", status_code=202)
    async def download_model(role: str):
        spec = get_spec(role)
        if spec.runtime in CUDA_ONLY_RUNTIMES and not settings.models.images_enabled:
            raise HTTPException(409, "Enable images in the model profile first")
        try:
            snapshot = setup.start_download(role, spec)
        except SetupBusy as exc:
            raise HTTPException(409, str(exc)) from exc
        return {"role": role, "setup": snapshot}

    @app.post("/api/models/{role}/install-runtime", status_code=202)
    async def install_runtime(role: str):
        spec = get_spec(role)
        extra = RUNTIME_EXTRAS[spec.runtime]
        try:
            snapshot = setup.start_install(extra)
        except SetupBusy as exc:
            raise HTTPException(409, str(exc)) from exc
        return {"role": role, "extra": extra, "setup": snapshot}

    @app.post("/api/models/{role}/config")
    async def configure_model(role: str, body: ModelOverride):
        get_spec(role)
        reject_if_downloading(role)
        fields = body.model_dump(exclude_unset=True)
        if not fields:
            raise HTTPException(422, "No override fields supplied")
        try:
            settings.save_override(role, fields)
        except (ValueError, TypeError) as exc:
            raise HTTPException(422, _explain(exc)) from exc
        return models_payload()

    @app.post("/api/models/{role}/config/reset")
    async def reset_model(role: str):
        get_spec(role)
        reject_if_downloading(role)
        try:
            settings.reset_override(role)
        except (ValueError, TypeError) as exc:
            raise HTTPException(422, _explain(exc)) from exc
        return models_payload()

    @app.get("/api/jobs")
    async def list_jobs():
        return store.list()

    @app.post("/api/jobs", status_code=201)
    async def create_job(body: JobInput):
        if settings.mode == "local" and not body.sources:
            raise HTTPException(
                422, "Local mode requires at least one source URL and excerpt"
            )
        return store.create(
            body.title,
            body.brief,
            [source.model_dump(mode="json") for source in body.sources],
            settings.mode,
            getattr(provider, "config_hash", None),
        )

    @app.get("/api/jobs/{job_id}")
    async def detail(job_id: str):
        return get_job(job_id)

    @app.get("/api/jobs/{job_id}/attempts")
    async def attempts(job_id: str):
        get_job(job_id)
        return store.attempts(job_id)

    @app.get("/api/jobs/{job_id}/artifacts/{artifact_id}")
    async def artifact(job_id: str, artifact_id: str):
        get_job(job_id)
        try:
            path = artifacts.resolve(job_id, artifact_id)
        except (ValueError, FileNotFoundError):
            raise HTTPException(404, "Artifact not found")
        return FileResponse(path, filename=artifact_id)

    def require_same_mode(job):
        if job.get("mode", "mock") != settings.mode:
            raise HTTPException(
                409, "Job belongs to a different provider mode; create a new draft"
            )

    def config_stale(job):
        return settings.mode == "local" and job.get("config_hash") != getattr(
            provider, "config_hash", None
        )

    @app.post("/api/jobs/{job_id}/run")
    async def run(job_id: str):
        job = get_job(job_id)
        require_same_mode(job)
        if config_stale(job):
            raise HTTPException(409, CONFIG_CHANGED)
        result = store.transition(job_id, ["draft", "failed"], "queued")
        if result is None:
            raise HTTPException(409, "Only draft or failed jobs can be started")
        return result

    @app.post("/api/jobs/{job_id}/restart")
    async def restart(job_id: str):
        job = get_job(job_id)
        require_same_mode(job)
        result = store.restart(job_id, getattr(provider, "config_hash", None))
        if result is None:
            raise HTTPException(
                409,
                "Only draft, failed, awaiting-approval, or completed jobs can be restarted",
            )
        return result

    @app.post("/api/jobs/{job_id}/approve")
    async def approve(job_id: str):
        get_job(job_id)
        result = store.transition(job_id, ["awaiting_approval"], "queued", approve=True)
        if result is None:
            raise HTTPException(409, "Job is not ready for approval")
        return result

    @app.delete("/api/jobs/{job_id}", status_code=204)
    async def delete_job(job_id: str):
        get_job(job_id)
        store.delete(job_id)
        return Response(status_code=204)

    return app


app = create_app()
