# Persistence

Sources: [`backend/app/store.py`](../backend/app/store.py),
[`backend/app/db/jobs.py`](../backend/app/db/jobs.py),
[`backend/app/db/platform.py`](../backend/app/db/platform.py),
[`backend/app/db/engine.py`](../backend/app/db/engine.py),
[`backend/migrations/`](../backend/migrations).

## Responsibility

SQLAlchemy engine, Alembic migrations, v1 job documents, control-plane tables,
legacy SQLite `jobs` JSON import, exclusive worker lock.

## Public surface

**v1 (pipeline):** `video_jobs`, `video_stages`, `stage_attempts`.
`Store`: `list`, `get`, `save`, `create`, `transition`, `restart`, `claim`,
`recover`, `start_attempt` / `finish_attempt`, `attempts`, `worker_lock`.

**Control plane (schema now, little pipeline use):** `channels`,
`channel_configs`, `video_projects`, `workflow_runs`, `workflow_events`,
`assets`, plus cost/alert/gpu job tables in `platform.py` / migration `0002`.

Default SQLite: `backend/data/jobs.sqlite3`. `DATABASE_URL` takes precedence.
PostgreSQL URLs starting `postgresql://` are rewritten to `postgresql+psycopg://`.

Revisions: `0001_relational_state`, `0002_control_plane`.

`python -m app.database` migrates and prints dialect + job count.

## How it is called

`Store(url)` in `create_app`. Lifespan takes `worker_lock()` when
`RUN_WORKER=true`.

## Invariants

- PostgreSQL: `pg_try_advisory_lock(76329011)`; second worker raises.
- SQLite: `{database}.worker.lock` via `filelock`, timeout 0.
- Legacy import is idempotent and preserves original stage pipelines.
- Concurrent `transition` has one winner.

## Related tests

`test_database.py` (legacy import, concurrent transitions, worker lock,
optional Postgres via `TEST_DATABASE_URL`).

## Known limitations

Switching SQLite → Postgres does not copy data. Similarity/memory tables for
pgvector are not the live similarity path. Do not drop v1 tables until
cutover tests exist.
