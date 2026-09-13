# HTTP API

Sources: [`backend/app/main.py`](../backend/app/main.py),
[`backend/app/schemas.py`](../backend/app/schemas.py).

## Responsibility

Thin HTTP surface: CORS, health, system/governor dump, model inventory, job
CRUD, run/restart/approve, artifact download and promotion, series routes.
No fill/model arithmetic.

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
| POST | `/api/jobs` | Title, brief, sources, optional `series_id`/`theme_id`/`library_source_ids` (local requires ≥1 source after library copy) |
| GET | `/api/jobs/{id}` | Job + stages |
| GET | `/api/jobs/{id}/attempts` | Attempt history |
| GET | `/api/jobs/{id}/artifacts/{artifact_id}` | FileResponse; IDs cannot contain paths |
| POST | `/api/jobs/{id}/artifacts/{artifact_id}/promote` | `{name, kind}`; copies a `.png`/`.wav` stage media output into the job's series library. 201 new, 200 duplicate; 409 no series; 415 not promotable; 404 not a media output; 413 over cap |
| POST | `/api/jobs/{id}/run` | `draft`/`failed` → `queued`; 409 if local `config_hash` is stale or `series_stale` |
| POST | `/api/jobs/{id}/restart` | Wipe stages, rebind `config_hash` and the series snapshot, `queued`; not while queued/running |
| POST | `/api/jobs/{id}/approve` | `awaiting_approval` → `queued` + `approved_at` |
| DELETE | `/api/jobs/{id}` | 204; removes the job, its stage records, and attempts, and returns a linked idea to `backlog`. Any status. 404 unknown job |
| GET/POST | `/api/series` | List newest first / create `{name, slug?, description?}` (409 duplicate slug) |
| GET/PATCH/DELETE | `/api/series/{id}` | DELETE 409 while any job references the series |
| GET | `/api/series/{id}/jobs` | Jobs in the series (with `series_stale`) |
| GET/PUT | `/api/series/{id}/bible` | Current version (0 = never saved) / append a `SeriesBible` version |
| GET | `/api/series/{id}/bible/versions` | `{version, sha256, created_at}` newest first |
| GET/POST | `/api/series/{id}/themes` | `{name, blurb?, guidance?}` |
| PATCH/DELETE | `/api/series/{id}/themes/{theme_id}` | DELETE 409 while any job uses the theme |
| GET/POST | `/api/series/{id}/ideas` | GET adds `job_status`; POST `{title, pitch?, notes?, theme_id?}` |
| PATCH/DELETE | `/api/series/{id}/ideas/{idea_id}` | `status` only `backlog`/`dropped`; 409 once linked to a video |
| POST | `/api/series/{id}/ideas/{idea_id}/start` | `{sources?, library_source_ids?}` → 201 draft job; 409 unless backlog |
| GET | `/api/series/{id}/assets` | `?include_archived=true` to include archived |
| POST | `/api/series/{id}/assets` | Raw body upload, `Content-Type` = media type, `?name=&kind=`; 201 new, 200 duplicate, 413 over `SERIES_ASSET_MAX_BYTES`, 415 disallowed/mismatched |
| PATCH | `/api/series/{id}/assets/{asset_id}` | `{name?, kind?, status?}` (archive/restore; no hard delete) |
| GET | `/api/series/{id}/assets/{asset_id}/content` | Bytes; `Content-Disposition: attachment` (hash filename), `nosniff` |
| GET/POST | `/api/series/{id}/sources` | Reusable `Source` excerpts; 409 duplicate source id |
| DELETE | `/api/series/{id}/sources/{source_id}` | 204; existing jobs keep their copies |

CORS: `GET`/`POST`/`PUT`/`PATCH`/`DELETE`, origins from `CORS_ORIGINS` (default Vite `:3091`).

`JobInput`: title 1–160, brief ≤5000, ≤10 sources with unique ids,
`series_id`/`theme_id` (theme requires series; theme must belong to it, else
422), `library_source_ids` ≤10 (requires a series; merged sources must stay
unique and ≤10, else 422). Job payloads include `series_id`, `theme_id`,
`idea_id`, `series_context`, `series_hash`, and computed `series_stale`.
Series details: [series.md](series.md).

`ModelOverride`: all fields optional; `model_dump(exclude_unset=True)` so an
explicit `filename: null` clears the filename while omitted fields are left
alone. Setup state is `{state, started_at, ended_at, error, log}`.

## How it is called

`create_app()`; module-level `app = create_app()`. Tests use `TestClient`.

## Invariants

- 409 if job mode ≠ `PIPELINE_MODE`.
- Local create without sources → 422.
- Local `/run` with a stale `config_hash` → 409; `/restart` rebases the job.
- `/run` on a job whose series bible/theme changed → 409; `/restart` rebinds.
- Series uploads are allowlisted by type and magic bytes and served as
  attachments.
- Artifact resolve rejects `..` and absolute names.
- Runtime installs are only ever `uv sync --extra <allowlisted extra>`; no
  request field reaches the command line. Tokens are scrubbed from setup logs.

## Related tests

`test_health_and_system_and_metrics`, `test_local_pipeline_artifacts_and_explicit_render_boundary`,
`test_restart_clears_stages_and_rebases_config_hash`,
`test_models_endpoint_reports_setup_fields`,
`test_download_endpoint_runs_hub_in_background`,
`test_install_endpoint_uses_fixed_command`, `test_config_override_endpoints`,
`test_config_change_fails_in_flight_job`, `test_delete_job_removes_job_and_attempts`,
`test_delete_unknown_job_is_404`, pipeline tests in `test_pipeline.py`, series
tests in `test_series.py`.

## Known limitations

No auth. No OpenAPI client codegen. Bind loopback in development.
