# Implementation docs

Module-by-module reference for **Video Orchestrator** as it exists today.

The product is a local dashboard plus FastAPI worker: mock or local inference,
SQLite or PostgreSQL, optional Compose (Postgres, Redis, MinIO, Temporal).
Read [`README.md`](../README.md) first for how to run it.

[`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) is the phased roadmap. Nothing
else in `docs/` should describe unbuilt work as current.

## Where to start

| Doc | Read it when |
|---|---|
| [architecture.md](architecture.md) | Whole picture: worker, providers, Compose |
| [invariants.md](invariants.md) | Before changing GPU, publish, Governor, or evidence rules |
| [testing.md](testing.md) | Before writing or changing a test |

## Runtime

| Doc | Source | Owns |
|---|---|---|
| [architecture.md](architecture.md) | [`backend/app/main.py`](../backend/app/main.py), [`compose.yaml`](../compose.yaml) | Layout, current vs target control plane |
| [api.md](api.md) | [`main.py`](../backend/app/main.py), [`schemas.py`](../backend/app/schemas.py) | HTTP routes, CORS, health |
| [config.md](config.md) | [`config.py`](../backend/app/config.py), [`backend/config/`](../backend/config) | Env + layered YAML |
| [series.md](series.md) | [`app/series/`](../backend/app/series) | Shared bibles, themes, ideas, media + source libraries |
| [governor.md](governor.md) | [`app/governor/`](../backend/app/governor) | Deterministic channel policy |
| [persistence.md](persistence.md) | [`store.py`](../backend/app/store.py), [`app/db/`](../backend/app/db), Alembic | Jobs, stages, control-plane tables |
| [pipeline.md](pipeline.md) | [`local_provider.py`](../backend/app/local_provider.py) | Local stages, evidence, critics |
| [providers.md](providers.md) | [`providers.py`](../backend/app/providers.py) | `Provider` protocol and mock |
| [models.md](models.md) | [`app/models/`](../backend/app/models) | Hub, GPU queue, subprocess runner, CLI |
| [local-models.md](local-models.md) | `models.yaml`, GPU policy | Roles, 8 GB VRAM, download flow |
| [rendering.md](rendering.md) | `backend/app/rendering.py`, `renderer/` | Local Remotion/FFmpeg MP4 rendering |
| [artifacts.md](artifacts.md) | [`artifacts.py`](../backend/app/artifacts.py) | Content-hashed job files |
| [storage.md](storage.md) | [`app/storage/`](../backend/app/storage) | Local disk vs S3/MinIO |
| [orchestrator.md](orchestrator.md) | [`app/orchestrator/`](../backend/app/orchestrator) | Temporal health canary |
| [observability.md](observability.md) | [`observability.py`](../backend/app/observability.py), Redis | Logs, metrics, health probes |
| [domain.md](domain.md) | [`app/domain/`](../backend/app/domain) | v2 states, opportunity scoring |
| [workflows.md](workflows.md) | worker + `states.py` | v1 job machine (current); v2 labeled target |
| [logical-agents.md](logical-agents.md) | providers + catalog | Tool allowlists; what is vs is not built |
| [frontend.md](frontend.md) | [`frontend/src/`](../frontend/src) | Dashboard, polling, ModelPanel |
| [testing.md](testing.md) | [`backend/tests/`](../backend/tests) | pytest, fakes, no network |
| [invariants.md](invariants.md) | across modules | GPU, locks, approval, evidence |

## Keeping these docs true

These docs are part of the code contract, not a side artifact. See the
documentation section of [`AGENTS.md`](../AGENTS.md): any change to behaviour,
public API, config keys, schema, or invariants updates the matching file here
in the same change. A new module gets a new `docs/<module>.md` and a row in the
tables above.

Scoped agent rules (Cursor, Codex, Claude Code) live in
[`.agents/rules/`](../.agents/rules/).

Each module doc follows the same shape so a diff is easy to place:
responsibility, public surface, how it is called, invariants, related tests,
and known limitations.
