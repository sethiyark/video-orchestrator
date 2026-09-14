# Config

Sources: [`backend/app/config.py`](../backend/app/config.py),
[`backend/config/default.yaml`](../backend/config/default.yaml),
[`development.yaml`](../backend/config/development.yaml),
[`production.yaml`](../backend/config/production.yaml),
[`models.yaml`](../backend/config/models.yaml).

## Responsibility

Validated runtime settings. Secrets from the **environment** only. Channel
policy from layered YAML. Model roles from `models.yaml`.

## Public surface

`Settings`: `database_url`, `mode` (`mock`|`local`), `app_env`,
`channel_governor`, `models`, `model_overrides`, `model_overlay_path`, `cache_dir`, `artifact_dir`, `run_worker`,
`origins` (default Vite `http://localhost:3091` and `http://127.0.0.1:3091`),
`redis_url`, `temporal_target`, `storage_backend` (`local`|`s3`),
S3 fields (`s3_endpoint` default `http://127.0.0.1:9000`),
`series_asset_max_bytes` (default 52428800; must be positive), `log_format`.

Env (selected): `DATABASE_URL` (wins over `DATABASE_PATH`), `PIPELINE_MODE`,
`APP_ENV`, `MODEL_CONFIG`, `MODEL_OVERLAY`, `MODEL_CACHE_DIR`, `ARTIFACT_DIR`, `RUN_WORKER`,
`CORS_ORIGINS`, `REDIS_URL`, `TEMPORAL_TARGET`, `STORAGE_BACKEND`,
`S3_*`, `SERIES_ASSET_MAX_BYTES`, `LOG_FORMAT`, `LOG_LEVEL`, `HF_TOKEN` (download/inference child
stripping is in the runner).

`ModelConfig` forbids extra keys; stage routes must match required runtimes:
LLM stages → `llama_cpp`; narration → `kokoro | qwen_tts`; alignment →
`whisper | ctc_aligner`; similarity → `sentence_transformers`; assets →
`diffusers | diffusers_gguf` when `images_enabled`.

`ModelSpec`: `runtime`, `repo_id`, `revision`, `files`, `filename`,
`extra_repos` (`name`, `repo_id`, `revision`, `files`, `filename`), `device`
(`cpu|cuda|metal`), `context_size`, `max_tokens`, `gpu_layers`,
`think_toggle`, `priority`, `timeout_seconds`, `voice`, `speaker`, `speed`,
`steps`.

`Governor` (in `models.yaml`): `max_attempts` (worker retries per stage),
`critique_rounds`, `critic_temperature`, `min_script_score`, `max_rewinds`
(times the worker sends a failed stage back to an earlier one with
corrections, default 2; 0 disables), `min_research_confidence`, `max_similarity`, `max_images`,
`min_narration_fidelity`.

`MODEL_CONFIG` selects a hardware profile: `config/models.mac.yaml` or
`config/models.cuda-8gb.yaml` (see [local-models.md](local-models.md)).

`MODEL_OVERLAY` (default `backend/data/models.local.yaml`, gitignored) holds
dashboard overrides as `{"models": {role: {field: value}}}` and is merged over
the profile by `load_model_config(path, overlay_path)` using `_merge`. Only
`OVERRIDABLE_FIELDS` may appear: `repo_id`, `revision`, `filename`, `files`,
`device`, `gpu_layers`, `context_size`, `max_tokens`, `voice`, `speed`,
`steps`. `runtime`, `extra_repos`, routes, and the governor stay in the
profile. `Settings.save_override(role, fields)` validates the whole merged
`ModelConfig` first (raising `ValueError`), writes the overlay atomically,
then replaces `settings.models`; `reset_override(role)` drops the entry and
unlinks an empty file; `override_for(role)` returns the saved fields.
`RUNTIME_EXTRAS` maps each runtime to its `pyproject.toml` extra.

`load_channel_governor(env_name)` merges `default.yaml` with
`{env}.yaml`.

## How it is called

`Settings()` at `create_app` and CLI download. `save_override` / `reset_override`
from `POST /api/models/{role}/config[/reset]`.

## Invariants

Embedding runtime must be CPU. GGUF, Kokoro, and GGUF diffusion require
`filename`. `diffusers_gguf` requires `extra_repos` named `base` and
`text_encoder`. `metal` only for `llama_cpp`, `kokoro`, `qwen_tts`;
`diffusers*` only on `cuda`. Model file patterns cannot be absolute or contain
`..`. An invalid overlay fails `Settings()`; an invalid override is rejected
before anything is written.

## Related tests

`test_config_rejects_wrong_stage_runtime`, `test_device_and_runtime_rules`,
`test_hardware_profiles_validate`, `test_overlay_merges_over_profile`,
`test_overlay_rejects_non_overridable_fields`,
`test_save_and_reset_override_roundtrip`,
`test_invalid_override_rejected_and_nothing_written`,
`test_governor_enforces_caps_and_human_gates`.

## Known limitations

No dotenv loader in-process; operators export env. Compose injects values.
