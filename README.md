# Video Orchestrator

A local video production app for an English engineering explainer channel. React + TypeScript uses TanStack Start, Router, and Query. FastAPI manages a persisted pipeline backed by SQLAlchemy 2, Alembic, and either SQLite or PostgreSQL.

The dashboard supports drafts, pipeline progress, stage outputs, model readiness, source evidence, narration downloads, and approval before upload.

## Start locally

Requirements: Node.js 22.12+ (`nvm use`), Python 3.12+, and [uv](https://docs.astral.sh/uv/).

Terminal 1:

```sh
cd backend
uv sync
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Terminal 2:

```sh
cd frontend
npm ci
npm run dev
```

Open [the dashboard](http://localhost:3000) or [API docs](http://localhost:8000/docs).

The default is **mock mode**. It needs no GPU, model files, tokens, or Docker. Mock completion means a simulation finished; it produces no real video or upload.

## Database

SQLite defaults to `backend/data/jobs.sqlite3`. `DATABASE_PATH` remains supported for existing installations. `DATABASE_URL` takes precedence:

```sh
export DATABASE_URL='postgresql+psycopg://video:video_local_dev@localhost:5432/video_orchestrator'
```

Start an optional PostgreSQL server from the repository root:

```sh
docker compose up -d postgres
```

Wait for it to become healthy before starting the API. The Compose credentials are local development defaults; `POSTGRES_PASSWORD` can override the password. PostgreSQL data persists in the `postgres-data` volume.

Migrations run at API construction, or explicitly from `backend`:

```sh
uv run python -m app.database
```

Tables:

- `video_jobs`: durable state, source inputs, mode, configuration fingerprint, approval time.
- `video_stages`: ordered stages with individual status and JSON outputs.
- `stage_attempts`: execution history, failures, interrupted attempts, and model provenance.
- `alembic_version`: schema revision.

Existing JSON rows from the original SQLite `jobs` table are imported idempotently, preserving their IDs, outputs, approval state, and original stage order. The old table remains intact. New jobs use the expanded pipeline. Switching to PostgreSQL creates a separate database; it does **not** automatically copy the SQLite database. Back up existing data before an upgrade.

## Hugging Face and local models

Hugging Face supplies **model weights**. Inference runs locally; no hosted inference service or paid API is enabled.

Edit `backend/config/models.yaml` to change repositories, revisions, download patterns, device settings, context size, output limits, priorities, voice, speed, and stage routing without editing agent code. `MODEL_CONFIG` can point to another YAML file.

Configured roles:

- **fast:** SmolLM3 3B Q4 GGUF for evidence extraction and metadata.
- **quality:** Qwen3 8B Q4 GGUF for verification, outlines, scripts, independent critics, and storyboards.
- **narration:** Kokoro-82M for sentence-chunked WAV narration.
- **alignment:** faster-whisper small for segment and word timestamps.
- **embeddings:** all-MiniLM-L6-v2 on CPU for comparison with previous scripts.
- **images:** optional SDXL with FP16, CPU offload, VAE slicing and tiling. Disabled by default.

The API remains lightweight; each inference subprocess imports only its required runtime. From `backend`, install the optional dependency groups you need:

```sh
uv sync --extra llm --extra audio --extra embeddings
```

`llama-cpp-python` may compile native code. Its default build is CPU-only. On the intended NVIDIA Linux host, install the CUDA toolkit/compiler and build with CUDA enabled:

```sh
CMAKE_ARGS='-DGGML_CUDA=on' uv sync --extra llm --extra audio --extra embeddings --reinstall-package llama-cpp-python --no-binary-package llama-cpp-python
```

Then set `device: cuda` and `gpu_layers: -1` for the fast/quality roles. The default YAML uses CPU to remain portable. Leave embeddings on CPU; Kokoro and Whisper also default to CPU. VRAM fit and speed must be measured on the actual GPU; reduce context size or GPU layers if needed.

Kokoro's English phonemizer also needs the spaCy English package and `espeak-ng`. Install `espeak-ng` through your OS package manager, then:

```sh
.venv/bin/python -m spacy download en_core_web_sm
```

Prepare the configured model files explicitly:

```sh
.venv/bin/python -m app.models.cli list
.venv/bin/python -m app.models.cli download fast
.venv/bin/python -m app.models.cli download quality
.venv/bin/python -m app.models.cli download narration
.venv/bin/python -m app.models.cli download alignment
.venv/bin/python -m app.models.cli download embeddings
# Or: .venv/bin/python -m app.models.cli download all
```

**uv manages extras per invocation.** After installing extras, use the environment executables below (or repeat the same `--extra` options in every `uv run`) so uv does not remove optional packages from the environment.

Downloads can total several GB. `all` skips the disabled image role. Set `HF_TOKEN` in the shell for gated/private repositories, after accepting any required model license yourself. Tokens never appear in the dashboard and are removed from the child inference environment.

The download client resolves a repository revision to a commit, downloads only selected files, then atomically records a cache manifest. Pin `revision` to a commit for reproducible deployments. Inference consumes prepared snapshots with Hugging Face/Transformers offline mode enabled and does not download weights during a job.

The default cache is `backend/data/models`; override with `MODEL_CACHE_DIR`. The model panel reports cache and package presence, not a guarantee of hardware compatibility. Prepare models **before creating local jobs**. Changing model configuration or downloaded commits requires a new draft to avoid silently mixing generations across retries.

Start real local inference:

```sh
PIPELINE_MODE=local .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

For optional images, install `uv sync --extra llm --extra audio --extra embeddings --extra images`, set `images_enabled: true`, and prepare `images`. Images use the same exclusive inference queue. The current implementation uses Diffusers directly; ComfyUI is not connected.

## Pipeline and evidence

New jobs run:

```text
research → verification → outline → script → critique → storyboard
→ assets → narration → alignment → similarity → metadata → render
→ human approval → upload
```

Local jobs require source URLs and excerpts. The UI accepts one source; the API accepts up to ten. Source URLs are recorded but **not fetched**. Research extracts claims with exact quotations checked against those excerpts. A separate model verifies each claim; only claims meeting the configured confidence threshold reach the outline and writer. This is model assessment of supplied evidence, not independent web fact-checking.

Accuracy, retention, clarity, originality, and style critics use separate prompts. The minimum critic score and unresolved required changes determine acceptance. Revision loops are bounded by the governor. Corpus similarity uses normalized embeddings from the same model configuration and revision; it currently compares against all prior jobs with completed similarity outputs, not only published videos.

Storyboards accept a closed JSON schema: `DefinitionCard`, `AnimatedFlowDiagram`, `BulletReveal`, and optional `ImagePan`. They cannot contain arbitrary renderer code. Kokoro produces a concatenated WAV with chunk boundaries; Whisper produces segment and word timestamps. Final scene retiming remains a renderer integration task.

Stage JSON and media are saved under `ARTIFACT_DIR` (default `backend/data/artifacts`) with content hashes and model provenance. Inspect stage JSON and download narration in the dashboard. API endpoints include:

- `GET /api/models`: configured roles, routes, cache state, and inference queue.
- `GET /api/jobs/{id}/attempts`: attempt history and review artifacts on critic failure.
- `GET /api/jobs/{id}/artifacts/{artifact_id}`: saved JSON, WAV, or PNG files.

## Scheduling and recovery

One worker owns the database: a PostgreSQL advisory lock or SQLite file lock prevents two workers from starting against the same database. Use `RUN_WORKER=false` for additional API processes; run one worker process. The model scheduler supports priority, waiting timeouts, metadata, and cancellation. A shared cache lock also serializes model subprocesses across instances using that cache.

Each model call starts an isolated process and waits for its exit before releasing the resource. Failed, timed-out, and cancelled children are terminated and reaped. Linux children receive a parent-death signal if the API process is killed. Hard-kill cleanup on other operating systems is not guaranteed. Unrelated model servers are outside this scheduler's control.

A restart marks interrupted attempts/jobs as failed; queued jobs resume. Manual retry skips completed stages. Local inference failures get bounded retry/backoff; missing models, evidence-policy failures, and unimplemented integrations stop immediately. Mock retries remain manual.

## Current boundaries

Database support and local model adapters are implemented. The full autonomous operating system described in the brief is **not** complete:

- No Temporal **video** workflow yet (Phase 1 starts Temporal with a health canary only). No discovery/search connectors, external LLM escalation, YouTube analytics, or publishing scheduler yet.
- MinIO and Redis run in Compose; local `uvicorn` still defaults to disk artifacts and no Redis.
- pgvector is installed in the Compose Postgres image; similarity still uses application-side cosine on JSON embeddings until Phase 4.
- No Remotion/FFmpeg renderer or YouTube OAuth/upload adapter yet. In local mode, the job stops at `render` with a clear error after model artifacts are generated. It never reports a nonexistent render or sends an upload.
- The human approval gate remains mandatory. A real upload integration must bind approval to an exact rendered artifact and add idempotent upload recovery.
- No authentication. Keep the API bound to localhost for development.

## Optional Docker foundation stack

```sh
docker compose up --build
```

Starts PostgreSQL (pgvector), Redis, MinIO, Temporal, Temporal UI (`http://127.0.0.1:8088`), the API (`http://127.0.0.1:8000`), and a Temporal worker. The API image includes base dependencies and runs in mock mode. Persist app files in `video-data`; run the frontend locally. Native GPU inference is intended to run on the host until a CUDA image is added.

`make setup`, `make test`, and `make worker` are documented in the Makefile. `make run-sample-pipeline` lands in later phases.

## Verification

```sh
cd backend
uv run pytest
uv run ruff check app tests migrations
uv run ruff format --check app tests migrations
```

For PostgreSQL integration testing, set `TEST_DATABASE_URL` to a **disposable** PostgreSQL database. The integration test writes test rows and verifies the schema, state transitions, attempt provenance, and advisory lock.

```sh
cd frontend
npm run build
npm run typecheck
```

Tests use controlled model responses and fake runtime processes; they do not download or execute multi-GB models. Actual model quality, native dependency compatibility, and GPU behavior need validation on the target machine.

## Reference documentation

Implementation docs (code contract): [`docs/README.md`](docs/README.md). Shared
agent guide (Cursor, Codex, Claude Code): [`AGENTS.md`](AGENTS.md). Roadmap:
[`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md).

[Hugging Face downloads](https://huggingface.co/docs/huggingface_hub/package_reference/file_download), [llama-cpp-python](https://github.com/abetlen/llama-cpp-python), [Kokoro](https://github.com/hexgrad/kokoro), [faster-whisper](https://github.com/SYSTRAN/faster-whisper), [SQLAlchemy](https://docs.sqlalchemy.org/en/20/orm/quickstart.html), [TanStack Start](https://tanstack.com/start/latest/docs/framework/react/build-from-scratch).
