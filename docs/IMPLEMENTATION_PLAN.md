# Implementation plan

This file is the **roadmap**, not a description of the current tree. Current
behaviour lives in [`README.md`](README.md) (index) and the module docs.
Checkboxes are the source of progress. Update them when work lands.

## Phase 0 — Architecture

- [x] Inspect existing repository
- [x] Document current vs target architecture (`docs/architecture.md`)
- [x] Document workflows and states (`docs/workflows.md`)
- [x] Document agents and tool allowlists (`docs/logical-agents.md`)
- [x] Document local models / GPU (`docs/local-models.md`)
- [x] Define domain entities (see below + `app/db/platform.py`)
- [x] Define Channel Governor schema (`config/default.yaml`, `app/governor`)
- [x] Define provider interfaces (model, storage, TTS, later YouTube/search)
- [x] This roadmap

### Domain entities (normalized)

`channels`, `channel_configs`, `video_jobs` (v1), `video_stages`, `stage_attempts`, `video_projects`, `workflow_runs`, `workflow_events`, `topics`, `topic_scores`, `research_sources`, `claims`, `claim_sources`, `outlines`, `scripts`, `script_reviews`, `storyboards`, `scenes`, `assets`, `audio_tracks`, `renders`, `qc_runs`, `title_candidates`, `thumbnail_candidates`, `publication_records`, `analytics_snapshots`, `postmortems`, `experiments`, `experiment_assignments`, `channel_memories`, `alerts`, `cost_records`, `model_runs`, `gpu_jobs`.

Phase 1 persists the **control-plane** subset. Content tables arrive with the research-to-script workflow (Phase 3) and later phases.

## Phase 1 — Foundation

- [x] Layered YAML config (`default` / `development` / `production`)
- [x] Channel Governor module (agents cannot override)
- [x] v2 workflow state enum + legal transitions
- [x] PostgreSQL + pgvector image in Compose
- [x] SQLAlchemy models for control-plane tables
- [x] Alembic revision `0002_control_plane`
- [x] Redis client (optional URL)
- [x] MinIO / S3 object-store interface (local fallback)
- [x] Temporal Compose services + health workflow + worker entrypoint
- [x] Structured JSON logging
- [x] FastAPI `/api/health` dependency probes
- [x] Prometheus `/metrics`
- [x] Makefile
- [x] `docker compose up` starts postgres, redis, minio, temporal, api, worker
- [ ] Grafana (optional; not required for Phase 1 acceptance)

## Phase 2 — Local model layer

- [x] Model-provider config + subprocess llama.cpp (existing)
- [x] FAST/QUALITY routing via YAML (existing)
- [x] GPU scheduler (existing)
- [ ] Shared `ModelProvider` HTTP llama.cpp / Ollama
- [ ] Structured JSON generation helper + retries
- [ ] Prompt files + versions
- [ ] `model_runs` logging on every invocation
- [ ] `make test-llm` smoke test

## Phase 3 — Research to script

- [x] Local research / verify / outline / script / critics / storyboard (existing, excerpt-based)
- [ ] Opportunity scoring wired to discovery providers
- [ ] Web/search provider interfaces + SSRF-safe fetch
- [ ] Sources vs claims vs verifier split persisted to tables
- [ ] Angle agent
- [ ] Temporal `VideoProductionWorkflow` through script approval
- [ ] `make demo-script`
- [ ] Golden fixtures (topic → script)

## Phase 4 — Memory + similarity

- [x] Embedding role + cosine vs prior jobs (existing, JSON)
- [ ] pgvector store
- [ ] Channel memory retrieval API
- [ ] Topic / hook / outline / title similarity breakdown

## Phase 5 — Storyboard + TTS

- [x] Storyboard JSON schema (subset of primitives)
- [x] Kokoro narration + Whisper alignment (existing)
- [ ] Sentence-chunk provenance records
- [ ] Timed storyboard rewrite after alignment

## Phase 6 — Video engine

- [ ] Remotion project
- [ ] First primitives: Title, Question, DefinitionCard, AnimatedFlowDiagram, ComparisonCards, BrowserWindow, CodeEditor, ImagePan, Callout, Outro
- [ ] FFmpeg mux
- [ ] Sample 2–3 minute render
- [ ] `make render-sample`

## Phase 7 — QC

- [ ] ffprobe / silence / black-frame / asset / metadata checks
- [ ] Block upload on failed QC

## Phase 8 — Packaging

- [x] Metadata stage (existing, single title)
- [ ] Title candidate generation + scoring
- [ ] Descriptions, chapters, thumbnail concepts
- [ ] Programmatic thumbnail render

## Phase 9 — YouTube

- [ ] OAuth + provider interface
- [ ] Idempotent **private** upload
- [ ] Store YouTube video id before success
- [ ] `autonomous_publish: false`

## Phase 10 — Analytics

- [ ] Snapshot ingest at 1h/6h/24h/72h/7d/30d
- [ ] Baseline comparison

## Phase 11 — Closed loop

- [ ] Postmortem → memory → scoring / writer context
- [ ] Min-sample guards

## Phase 12 — Autonomous scheduler

- [ ] Discovery cadence
- [ ] Capacity + weekly governor caps
- [ ] Analytics / postmortem schedules

## Phase 13 — Dashboard

- [x] Job list, stages, models, artifacts, approval (existing)
- [ ] Overview (GPU, alerts, capacity)
- [ ] Human review queue actions
- [ ] System health view
- [ ] Dashboard authentication

## Phase 14 — Shorts

- [ ] Derive from long-form high-retention segments
- [ ] Vertical storyboard + 1080×1920
- [ ] Separate governor caps

## Tests (ongoing)

- [x] Pipeline, database, GPU, local provider fixtures
- [x] Governor unit tests
- [x] State-transition unit tests
- [x] Opportunity scoring unit tests
- [x] Object-store local backend tests
- [ ] Temporal workflow tests (Phase 3)
- [ ] MinIO / PostgreSQL integration in CI
- [ ] YouTube mock provider
- [ ] Golden prompt/schema tests

## Explicit non-goals

See `docs/logical-agents.md` § What we will not build.
