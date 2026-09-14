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
- [x] Structured JSON generation helper + retries (batched child, in-child repair)
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

- [x] Remotion project
- [x] FFmpeg mux
- [x] Sample 2–3 minute render
- [x] `make render-sample`
- [x] Chaptered scene engine (design below; steps 6.1–6.9 landed)

### Phase 6 design — chaptered scene engine

Goal: replace the single flat storyboard with LLM-planned **chapters**, a
closed library of richer scene components, one generated image per scene,
a reusable Remotion component library driven by a series brand kit, and a
manual image relay (Claude/Gemini Pro) that is the default image source.
Nothing here changes narration, alignment, the approval gate, or the
Governor's agent-immutability. Everything the model emits stays a closed,
schema-validated data enum; the renderer never receives code.

**Baseline.** The uncommitted working-tree changes (required `ImagePan`
count, image prompt wording, assets message) are the starting point. The
"at least one ImagePan" rule is superseded by 6.2 (every scene carries an
image prompt), so that rewind is removed again in 6.2.

#### 6.1 Storyboard schema: chapters + new components

`backend/app/schemas.py`

- `Chapter`: `chapter_id` (`chapter_NN`), `title` ≤80, `tagline` ≤160,
  `first_scene`/`last_scene` (scene ids, contiguous, non-overlapping, cover
  every scene), `hero_prompt` 10–300, `accent` (0–11 index into the theme
  palette). 1–12 chapters. `Storyboard.chapters: list[Chapter]`.
- `SceneBase.image_prompt: str = ""` (≤300). The provider requires it
  non-empty on every scene when images are enabled; the schema keeps it
  optional so mock mode and old jobs still validate.
- New components (all props are bounded strings/lists, `extra="forbid"`):
  - `ChapterTitle {title, subtitle}` — full-frame opener a chapter may use
    for its hook sentence.
  - `Outro {title, takeaways[1..4], next_topic?}` — the storyboard's last
    scene must be an `Outro` (provider check, rewind to storyboard).
  - `CodeBlock {title, language ∈ closed enum (python, typescript,
    javascript, go, rust, bash, sql, yaml, json, c, cpp, java, text),
    code ≤1200, highlight_lines[≤6]}`.
  - `Terminal {title, lines[1..12] of {kind ∈ (command, output), text ≤120}}`.
  - `Comparison {title, left{label, points[1..4]}, right{label, points[1..4]}}`.
  - `StatCounter {title, stats[1..4] of {value ≤16, label ≤60}}` — the
    renderer animates the leading number if `value` parses, else fades it.
  - `Timeline {title, events[2..6] of {label ≤40, text ≤120}}`.
  - `Callout {title, quote ≤300, claim_id}` — `quote` must be located in
    that verified claim's stored quote by `locate_quote` (same rule as
    research); a Callout that is not evidence fails closed with
    `rewind_to="storyboard"`.
  - `IconGrid {title, items[2..6] of {icon ∈ closed enum of 24 names,
    label ≤40}}` — icons are inline SVGs in the renderer, never URLs.
- Matching `*Plan` classes for `StoryboardChunk`; `PlannedScene` union grows
  to 14 members. `MAX_SCENE_SENTENCES` stays 6, scene cap stays 120.
- `backend/app/series/schema.py` `Component` literal, `frontend/src/lib/api.ts`
  `ComponentName`, and `BibleFields.tsx` gain the nine new names.

#### 6.2 Storyboard stage: chapter planning pass

`backend/app/local_provider.py` `storyboard()`

1. **Chapter plan** (one `ChapterPlan` request, `budget()`-checked): the
   model receives the numbered sentences, the outline titles/purposes as
   hints, and series guidance; returns `chapters[1..12]` as
   `first_sentence/last_sentence + title + tagline + hero_prompt`.
   `cover_sentences` snaps them to contiguous coverage (reuse). A script
   too long for one request falls back to outline sections as chapters
   (logged at warning; a job with no outline sections is `ReviewRequired`).
2. **Scene plan** runs per chapter with the existing 16-sentence chunking,
   chunks never cross a chapter boundary. Each request also carries
   `chapter {number, title, tagline}` and `available_components`. The
   prompt now asks for one concrete `image_prompt` per scene (subject,
   composition, labels; no artist names; no text longer than a label) and
   for a `Callout` only where `claim_id` is a verified claim.
3. Assembly numbers scenes and chapters, copies narration, computes
   durations as today, and validates: every chapter non-empty, the last
   scene is `Outro`, `ChapterTitle` appears only as a chapter's first
   scene, `Callout` quotes locate, `SeriesAsset` ids are active, and
   `image_prompt` is present on every scene when images are enabled
   (`ReviewRequired`, `rewind_to="storyboard"` with the offending scene id).

Manual routing for `storyboard` works unchanged: the chapter pass is one
more `llm_batch` call in sequence.

#### 6.3 Assets stage: one image per scene, batched, cached, or relayed

`backend/app/local_provider.py` (assets), `backend/app/models/runtime.py`,
`backend/app/models/runner.py`, `backend/app/artifacts.py`,
`backend/app/config.py`, Governor.

- **Budget.** `Governor.max_images` bound 30→120 (`models.mac.yaml` and
  `models.cuda-8gb.yaml` set 120; `models.yaml` keeps 3);
  `BudgetSection.max_image_generations_per_video` bound 100→120 and
  `config/default.yaml` set to 120. The stage enforces
  `min(max_images, max_image_generations_per_video)`. Scenes past the cap
  are recorded as `{scene_id, fallback: "chapter_hero"}` and render on the
  chapter hero plate; chapter heroes are generated first, then scenes in
  order, so a cap never leaves a chapter without an image.
- **Local batching.** The diffusers runtime accepts
  `{"prompts": [{"prompt", "output_path", "seed"}]}` and generates every
  image with one pipeline load; per-item failures are returned as
  `{"error"}` entries. The stage sends batches of `IMAGE_BATCH = 24` so one
  child stays inside `timeout_seconds`. Seeds are `42 + index`.
- **Cache across jobs.** `Artifacts.cache_image(key)` /
  `Artifacts.store_cached(key, path)` under `data/artifacts/cache/images/`,
  keyed by sha256 of `(final prompt incl. series image_style, model
  fingerprint, seed, 768×768)`. A hit is copied (not linked) into the job
  folder and adopted, so job artifacts stay self-contained; `assets.images[]`
  records `cache: hit|miss`. Same prompt + same model ⇒ same image in later
  jobs of that series (and, because the series style is inside the prompt,
  only incidentally across series). Restart with `POST …/restart` keeps
  the cache; a new `?purge_image_cache=true` query is out of scope.
- **Manual image relay (default).** `routes.assets: "manual"` is now valid
  (`validate_routes`), and **both shipped image-enabled profiles default to
  it**; SDXL/FLUX stay one YAML edit away. The stage raises
  `ManualStepRequired` with a prompt document listing every needed image
  (`chapter_NN` heroes and `scene_NNN`), each with its full prompt text,
  the expected size (1536×864, 16:9; the renderer letterboxes anything
  else), and paste-back instructions. The worker parks the job exactly as
  the LLM relay does; `output.manual` carries `expected_images:
  [{id, prompt}]`. New endpoint `POST /api/jobs/{id}/stages/assets/
  manual-images` (multipart, one or more files, field name = scene or
  chapter id; ≤ 8 MB each; png/jpeg/webp by magic bytes, reusing
  `series.library._matches`) validates, adopts, appends to
  `output.manual.images`, and returns what is still missing. When every
  expected id has a file, the same request requeues the job.
  `POST …/manual-images/skip` marks remaining ids as `chapter_hero`
  fallbacks (a chapter hero itself cannot be skipped). No model, token, or
  network is involved; the user relays through their own Claude/Gemini tab.
  Pinned `SeriesAsset` references, the brand kit (6.6) and music (6.5)
  are pinned by the same stage before it parks.
- **Mock provider** emits chapters, `image_prompt`s and one generated
  gradient PNG per scene (pure-Python PNG writer, no Pillow) so the mock
  pipeline and dashboard exercise the same shapes.

#### 6.4 Renderer component library

`renderer/src/` is split into:

```
src/index.jsx           registerRoot, Composition, manifest → Video
src/theme.mjs           palette/accents/fonts from manifest.brand, defaults
src/motion.mjs          clamp/ease/revealAt (unchanged) + transition curves,
                        counter(), typewriter(), dissolve/wipe/slide masks
src/highlight.mjs       deterministic tokenizer for the CodeBlock language enum
                        (keywords, strings, comments, numbers); no eval, no deps
src/icons.jsx           closed inline-SVG icon set (24 names)
src/fonts.mjs           vendored Inter + JetBrains Mono woff2 (OFL, from the
                        @fontsource packages) injected as @font-face with a
                        bounded wait; no network
src/layout/Frame.jsx    dark ground, blurred/darkened image plate, grid, vignette
src/layout/Header.jsx   series name, chapter label, scene counter
src/layout/Rail.jsx     chapter-segmented progress rail (chapter ticks)
src/layout/Opener.jsx   2.4 s chapter opener overlay (number, title, tagline,
                        hero plate wipe) on a chapter's first scene when that
                        scene is not a ChapterTitle
src/layout/Captions.jsx word-highlight captions from manifest.words
src/layout/Transition.jsx  per-scene enter/exit; cross-dissolve, slide, wipe
                        chosen deterministically from (chapter, scene index);
                        chapter boundaries use a full wipe
src/components/*.jsx    one file per storyboard component (14)
```

Every component takes `{scene, chapter, theme, frame, frames}` and only
renders escaped text, numbers, and library SVG. Transitions are implemented
in-house by extending each scene `Sequence` by `OVERLAP = 10` frames and
layering the incoming scene above the outgoing one; the alignment timeline
and narration audio are untouched. `motion.mjs` stays browser-free so
`test_rendering.py` can keep exercising timing in Node. Pinned additions:
`@fontsource/inter` and `@fontsource/jetbrains-mono`; nothing else.

Manifest (`backend/app/rendering.py`) gains `chapters[]` (with
`from/frames` and hero image file), per-scene `image` for every scene that
has one (plate for text components, subject for `ImagePan`), `words[]`
(`{text, from, frames, scene}` from the `timed` list already computed in
`timeline()`), `brand` (6.6), `music` (6.5), and `captions: bool`. Missing
required media still fails before Node starts.

#### 6.5 Captions and music bed

- `JobInput.render: {captions: bool = true, music_asset_id: str | null}`
  stored on the job; `PATCH /api/jobs/{id}/render` may change it before the
  render stage runs (409 afterwards). Dashboard exposes both on job create.
- Captions: sentence-grouped lines (≤ 8 words), current word emphasised,
  positioned above the rail; skipped when `captions` is false.
- Music: `music_asset_id` must be an active `music` asset in the job's
  series (wav/mp3); assets pins it by sha256; render copies it as
  `music.<ext>` and Remotion plays it looped with a per-frame volume
  envelope derived from `words[]` (‑16 dB under speech, ‑7 dB in gaps,
  60-frame fades, 2 s tail). No bundled or fetched music.

#### 6.6 Series brand kit

`backend/app/series/schema.py` `VisualGuide` gains `logo_asset_id`,
`intro_asset_id`, `outro_asset_id`, `music_asset_id` (all optional ids
of active series assets, validated on `put_bible`). `palette` (≤12 hex)
becomes the chapter accent list; `preferred_components` covers the new
enum. The assets stage pins each referenced brand asset by sha256 into
`assets.brand`; render verifies the hashes exactly like `SeriesAsset`.
Renderer: logo watermark in `Header`, intro plate (image, ≤ 3 s programmatic
reveal) before the first scene by shifting every `from` and the audio by
`intro_frames`, outro plate behind the `Outro` scene. Standalone jobs use
the default theme. Frontend `BibleFields` gets pickers populated from the
series library.

#### 6.7 Sample, docs, frontend

- `render_sample.py` becomes a three-chapter sample using all 14 components,
  captions from its synthetic segments, generated gradient plates, and no
  models; `make render-sample` stays the offline smoke test.
- Docs updated in the same change: `rendering.md`, `pipeline.md`,
  `config.md`, `governor.md`, `series.md`, `artifacts.md`, `api.md`,
  `frontend.md`, `invariants.md` (new: Callout quotes must locate in a
  verified claim; code/terminal text is displayed, never executed; manual
  images are magic-byte checked and size-capped; music and brand media come
  only from the series library; the image cache is keyed by prompt +
  model fingerprint and never by URL).
- Dashboard: job page shows chapters with scene thumbnails, the manual image
  relay panel (prompt list with copy buttons, per-id upload, missing count,
  skip-to-hero), render options on create, brand kit pickers in the bible.

#### 6.8 Tests (all offline, fake runners)

- Schema: chapter coverage, component bounds, `Callout` location, `Outro`
  last, `ChapterTitle` placement, icon/language enums reject unknown values.
- Storyboard stage: chapter pass + per-chapter chunking, outline fallback,
  every rewind reason.
- Assets: batch payload shape and seeds, cap ordering (heroes first),
  cache hit copies rather than links, manual relay park/upload/skip/requeue,
  rejected files (HTML renamed .png, oversize, unknown id), brand/music pinning.
- Rendering: manifest `words[]`/`chapters[]`, intro offset, missing plate
  fails before Node, `motion.mjs` transitions and `counter()` in Node.
- Renderer: `highlight.mjs` tokenizer golden tests in Node; a Remotion
  still-frame test per component behind the same Node/Chrome skip as today.
- API: `manual-images` and `render` endpoints; `validate_routes` accepts
  `assets: manual`.

#### 6.9 Verification on this Mac

`make setup-renderer` (if needed) → `uv run pytest`, `ruff`, `pnpm
typecheck`/`build` → `make render-sample` real Remotion/Chrome render →
send the MP4 plus per-component frames. A full local LLM job is not part of
verification: this machine's Hub cache holds no Qwen/Kokoro/Whisper/SDXL
weights, so the pipeline path is proven by the offline tests and the mock
pipeline in the browser, and the manual relay by a mock-mode job end to end.

**Out of scope for this phase:** QC checks (Phase 7), thumbnails
(Phase 8), per-chapter MP4 caching, vertical layouts (Phase 14), any
network fetch of images, fonts, or music.

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
