# HTTP API

Sources: [`backend/app/main.py`](../backend/app/main.py),
[`backend/app/schemas.py`](../backend/app/schemas.py).

## Responsibility

Thin HTTP surface: CORS, health, system/governor dump, model inventory, job
CRUD, run/restart/approve, artifact download. No fill/model arithmetic.

## Public surface

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/api/health` | Worker, database, storage, redis, temporal probes |
| GET | `/metrics` | Prometheus text |
| GET | `/api/system` | Governor dump (external provider name hidden unless enabled) |
| GET | `/api/models` | Roles, cache, GPU queue, per-role `setup`, `spec`, `overridden`, `extra`, `install_command`; top-level `setup_running`, `overlay_path` |
| POST | `/api/models/{role}/download` | 202 `{role, setup}`; starts `ModelHub.download` in the background. 404 unknown role; 409 already running or image role disabled |
| POST | `/api/models/{role}/install-runtime` | 202 `{role, extra, setup}`; runs `uv sync --extra <extra>`. 409 already running |
| POST | `/api/models/{role}/config` | `ModelOverride` body (subset of `OVERRIDABLE_FIELDS`, `extra="forbid"`); saves the overlay and returns the `/api/models` payload. 422 invalid/empty; 409 while that role downloads |
| POST | `/api/models/{role}/config/reset` | Drops the role's override; returns the `/api/models` payload |
| GET | `/api/jobs` | Newest first |
| POST | `/api/jobs` | Title, brief, sources (local requires ≥1 source) |
| GET | `/api/jobs/{id}` | Job + stages |
| GET | `/api/jobs/{id}/attempts` | Attempt history |
| GET | `/api/jobs/{id}/artifacts/{artifact_id}` | FileResponse; IDs cannot contain paths |
| POST | `/api/jobs/{id}/run` | `draft`/`failed` → `queued`; 409 if local `config_hash` is stale |
| POST | `/api/jobs/{id}/restart` | Wipe stages, rebind `config_hash`, `queued`; not while queued/running |
| POST | `/api/jobs/{id}/approve` | `awaiting_approval` → `queued` + `approved_at` |

CORS: `GET`/`POST`, origins from `CORS_ORIGINS` (default Vite `:3091`).

`JobInput`: title 1–160, brief ≤5000, ≤10 sources with unique ids.

`ModelOverride`: all fields optional; `model_dump(exclude_unset=True)` so an
explicit `filename: null` clears the filename while omitted fields are left
alone. Setup state is `{state, started_at, ended_at, error, log}`.

## How it is called

`create_app()`; module-level `app = create_app()`. Tests use `TestClient`.

## Invariants

- 409 if job mode ≠ `PIPELINE_MODE`.
- Local create without sources → 422.
- Local `/run` with a stale `config_hash` → 409; `/restart` rebases the job.
- Artifact resolve rejects `..` and absolute names.
- Runtime installs are only ever `uv sync --extra <allowlisted extra>`; no
  request field reaches the command line. Tokens are scrubbed from setup logs.

## Related tests

`test_health_and_system_and_metrics`, `test_local_pipeline_artifacts_and_explicit_render_boundary`,
`test_restart_clears_stages_and_rebases_config_hash`,
`test_models_endpoint_reports_setup_fields`,
`test_download_endpoint_runs_hub_in_background`,
`test_install_endpoint_uses_fixed_command`, `test_config_override_endpoints`,
`test_config_change_fails_in_flight_job`, pipeline tests in
`test_pipeline.py`.

## Known limitations

No auth. No OpenAPI client codegen. Bind loopback in development.
