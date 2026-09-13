# HTTP API

Sources: [`backend/app/main.py`](../backend/app/main.py),
[`backend/app/schemas.py`](../backend/app/schemas.py).

## Responsibility

Thin HTTP surface: CORS, health, system/governor dump, model inventory, job
CRUD and run/approve, artifact download. No fill/model arithmetic.

## Public surface

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/api/health` | Worker, database, storage, redis, temporal probes |
| GET | `/metrics` | Prometheus text |
| GET | `/api/system` | Governor dump (external provider name hidden unless enabled) |
| GET | `/api/models` | Roles, cache, GPU queue |
| GET | `/api/jobs` | Newest first |
| POST | `/api/jobs` | Title, brief, sources (local requires ≥1 source) |
| GET | `/api/jobs/{id}` | Job + stages |
| GET | `/api/jobs/{id}/attempts` | Attempt history |
| GET | `/api/jobs/{id}/artifacts/{artifact_id}` | FileResponse; IDs cannot contain paths |
| POST | `/api/jobs/{id}/run` | `draft`/`failed` → `queued` |
| POST | `/api/jobs/{id}/approve` | `awaiting_approval` → `queued` + `approved_at` |

CORS: `GET`/`POST`, origins from `CORS_ORIGINS` (default Vite `:3091`).

`JobInput`: title 1–160, brief ≤5000, ≤10 sources with unique ids.

## How it is called

`create_app()`; module-level `app = create_app()`. Tests use `TestClient`.

## Invariants

- 409 if job mode ≠ `PIPELINE_MODE`.
- Local create without sources → 422.
- Artifact resolve rejects `..` and absolute names.

## Related tests

`test_health_and_system_and_metrics`, `test_local_pipeline_artifacts_and_explicit_render_boundary`,
pipeline tests in `test_pipeline.py`.

## Known limitations

No auth. No OpenAPI client codegen. Bind loopback in development.
