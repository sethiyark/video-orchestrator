# Testing

Source: [`backend/tests/`](../backend/tests).

## Responsibility

pytest from `backend/` (`pythonpath = ["."]`). Default suite needs no GPU,
no Hugging Face download, no live Temporal.

## Public surface

| File | Owns |
| --- | --- |
| `test_pipeline.py` | Mock worker, approval, retry, interrupt recovery |
| `test_local_provider.py` | Grounding, critics, storyboard schema, unverified claims |
| `test_local_api.py` | Local artifacts, render boundary |
| `test_models.py` | Config, hub pin, GPU queue, runner kill |
| `test_database.py` | Legacy import, locks; Postgres if `TEST_DATABASE_URL` |
| `test_control_plane.py` | Governor, scoring, states, health, object store |

Fakes: controlled model JSON and fake runtime processes.

## How it is called

```bash
cd backend
uv run pytest
uv run ruff check app tests migrations
```

Frontend: `npm run typecheck` / `npm run build` (not pytest).

## Invariants

Tests never hit the network or download weights. Do not skip lock or
approval tests to land a change.

## Known limitations

No Playwright. MinIO/Temporal/Postgres not required in default CI. Real model
quality is out of band on the GPU host.
