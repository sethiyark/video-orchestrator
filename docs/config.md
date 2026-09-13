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
`channel_governor`, `models`, `cache_dir`, `artifact_dir`, `run_worker`,
`origins` (default Vite `http://localhost:3091` and `http://127.0.0.1:3091`),
`redis_url`, `temporal_target`, `storage_backend` (`local`|`s3`),
S3 fields (`s3_endpoint` default `http://127.0.0.1:9000`), `log_format`.

Env (selected): `DATABASE_URL` (wins over `DATABASE_PATH`), `PIPELINE_MODE`,
`APP_ENV`, `MODEL_CONFIG`, `MODEL_CACHE_DIR`, `ARTIFACT_DIR`, `RUN_WORKER`,
`CORS_ORIGINS`, `REDIS_URL`, `TEMPORAL_TARGET`, `STORAGE_BACKEND`,
`S3_*`, `LOG_FORMAT`, `LOG_LEVEL`, `HF_TOKEN` (download/inference child
stripping is in the runner).

`ModelConfig` forbids extra keys; stage routes must match required runtimes.

`load_channel_governor(env_name)` merges `default.yaml` with
`{env}.yaml`.

## How it is called

`Settings()` at `create_app` and CLI download.

## Invariants

Embedding runtime must be CPU. GGUF/Kokoro require `filename`. Model file
patterns cannot be absolute or contain `..`.

## Related tests

`test_config_rejects_wrong_stage_runtime`, `test_governor_enforces_caps_and_human_gates`.

## Known limitations

No dotenv loader in-process; operators export env. Compose injects values.
