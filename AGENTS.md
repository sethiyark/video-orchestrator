# AGENTS.md

Shared project guidance for coding agents (Cursor, Codex, Claude Code, and others).
Claude Code loads this file via `@AGENTS.md` in `CLAUDE.md` — keep that pointer, do not copy this content there.

**Scoped rules** (same text, three loaders — edit [`.agents/rules/`](.agents/rules/) first):

| File | When | How it is loaded |
|---|---|---|
| [`.agents/rules/docs.md`](.agents/rules/docs.md) | Always | Cursor `alwaysApply`; Claude `.claude/rules/docs.md`; Codex `docs/AGENTS.md` |
| [`.agents/rules/python.md`](.agents/rules/python.md) | Python trees | Cursor glob `**/*.py`; Claude `paths:`; Codex `backend/`, `backend/tests/`, `backend/migrations/` `AGENTS.md` |
| [`.agents/rules/frontend.md`](.agents/rules/frontend.md) | UI | Cursor glob; Claude `paths:`; Codex `frontend/AGENTS.md` |

## Project

**Video Orchestrator** — a local, single-user production app for English engineering explainers. FastAPI + SQLAlchemy backend, React/TypeScript dashboard (TanStack Start). Hugging Face supplies **weights**; inference is local. The default `PIPELINE_MODE=mock` needs no GPU, model files, or tokens.

`docs/` is the module-by-module implementation reference and is part of the code contract — see [Documentation](#documentation). Start at [`docs/README.md`](docs/README.md).

[`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md) is the phased roadmap. It is **not** a description of the current tree. Do not implement from it unless the user explicitly asks.

## Stack

- **Backend: Python >= 3.12**, managed with **uv**. FastAPI, SQLAlchemy 2, Alembic. Package layout: [`backend/`](backend/).
- **Frontend: React + TypeScript + Vite**, TanStack Start / Router / Query. **pnpm** via Corepack (`frontend/package.json` `packageManager`). Node >= 22.12.
- **Persistence:** SQLite at `backend/data/jobs.sqlite3` by default (`DATABASE_PATH` / `DATABASE_URL`). Optional PostgreSQL via Compose.
- **Localhost development.** No dashboard auth yet. Bind the API and UI to loopback.

## Commands

From the repository root, `make setup` then `make dev` starts the API (`127.0.0.1:8091`) and dashboard (`127.0.0.1:3091`). Ctrl+C stops both. `make dev-api` / `make dev-ui` run one process.

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8091
uv run pytest
uv run ruff check app tests migrations
uv run python -m app.database

cd frontend
corepack enable
corepack prepare
pnpm install --frozen-lockfile
pnpm dev             # :3091
pnpm typecheck
pnpm build
```

Default pipeline is **mock**. Local inference:

```bash
cd backend
uv sync --extra llm --extra audio --extra embeddings
PIPELINE_MODE=local .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8091
```

Optional foundation stack from the repo root: `docker compose up --build` (Postgres, Redis, MinIO, Temporal, API in mock mode, Temporal worker). Frontend still runs locally.

Tests must not download multi-GB models or call the network. Keep it that way.

## Documentation

`docs/` documents the implementation, one file per module, indexed by [`docs/README.md`](docs/README.md). Treat it like the tests: it is part of the change, not a follow-up.

- **Every change that alters behaviour, a public interface, a config key, a schema, or an invariant updates the matching `docs/` file in the same change.** A pure refactor with no observable change does not, unless it moves something a doc points at.
- **A new module gets a new `docs/<module>.md`** following the existing shape (responsibility, public surface, how it is called, invariants, related tests, known limitations) plus a row in `docs/README.md`.
- **Keep `docs/` describing what the code does now.** Never document planned or unbuilt work as current. The implementation plan is the roadmap.
- Line-numbered code references in docs must match the file they cite.
- Do not create new top-level markdown files or summary documents. Extend `README.md` (operator-facing), `docs/` (implementation), this file (always-on guide), or [`.agents/rules/`](.agents/rules/). After changing a scoped rule, keep the Cursor `.mdc` mirror in [`.cursor/rules/`](.cursor/rules/) aligned. Claude and Codex pick up the canonical files through [`.claude/rules/`](.claude/rules/) and nested `AGENTS.md` symlinks.

## Working agreement

Rules for any agent (Cursor, Codex, Claude Code) working in this repo.

**Before editing**

- Read the relevant `docs/` file and the surrounding code first. Do not invent APIs, config keys, Temporal video workflows, or YouTube calls — resolve them from the source.
- Make the smallest change that satisfies the request. No drive-by refactors, renames, reformatting, or dependency swaps.
- Prefer extending the existing in-process worker (`create_app` + `Provider.execute`) over adding a parallel execution path.
- If the request is ambiguous in a way that changes publish, GPU, or Governor behaviour, ask before implementing.

**While editing**

- Match the surrounding style. Type hints on public functions; PEP 604 unions.
- Logging via `log = logging.getLogger(__name__)`.
- New Python dependencies go through uv / [`backend/pyproject.toml`](backend/pyproject.toml). Frontend dependencies go through pnpm (`frontend/package.json`).

**Tests**

- Behaviour changes come with tests in [`backend/tests/`](backend/tests/).
- Tests never touch the network and never download model weights. Fake runners / controlled JSON as existing tests do.

**Verifying**

- Backend: `uv run pytest` and `uv run ruff check app tests migrations` from `backend/`.
- Frontend: `pnpm typecheck` / `pnpm build`, and verify UI in a browser end to end when you change it.
- Report the result honestly, including what you did not run.

**Safety**

- Never execute LLM-generated code or shell. Storyboard JSON is a closed component enum.
- Never report a successful render or YouTube upload that did not happen.
- Never persist or echo `HF_TOKEN`, `.env`, or OAuth secrets in logs, URLs, SQLite, or the UI.
- Never commit unless asked. Never skip hooks, amend pushed commits, force-push, or rewrite shared history.

## Architecture

Full detail is in [`docs/`](docs/README.md) — start with [`docs/architecture.md`](docs/architecture.md).

```
create_app → Store (migrate) → MockProvider | LocalProvider
          → in-process worker (claim → execute stages)
          → REST /api/* → thin React dashboard
```

- [`backend/app/main.py`](backend/app/main.py) — HTTP, CORS, health, worker lifespan. No model arithmetic.
- [`backend/app/store.py`](backend/app/store.py) — jobs, stages, attempts, worker lock.
- [`backend/app/local_provider.py`](backend/app/local_provider.py) — local stages through `LocalRunner`.
- [`backend/app/models/gpu.py`](backend/app/models/gpu.py) — exclusive inference queue.
- [`frontend/src/`](frontend/src/) — display and commands only.

Temporal today: [`HealthWorkflow`](backend/app/orchestrator/workflows.py) connectivity canary. Video production still runs in-process.

## Invariants

- **One GPU-heavy job at a time** (`GPUManager.acquire`). Unload hooks run on failure. Embeddings stay on CPU.
- **One worker per database** (PostgreSQL advisory lock or SQLite file lock). Extra API processes use `RUN_WORKER=false`.
- **Upload requires `approved_at`.** `autonomous_publish` defaults to false. Governor is YAML, not agent-mutable.
- **Local jobs need source excerpts.** URLs are recorded, not fetched. Fabricated quotes fail closed.
- **Render/upload are real integrations or explicit errors.** Mock may say “simulated”; local mode must not invent MP4/YouTube success.
- **Secrets from the environment only.** Tokens stripped from inference child env.

Owning tests live in [`backend/tests/`](backend/tests/). Details: [`docs/invariants.md`](docs/invariants.md).

## Known limitations (deliberate)

No YouTube adapter, no discovery search, no pgvector similarity store yet, no dashboard auth. Do not “fix” a documented limitation as a side effect of another change.
