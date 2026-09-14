# Frontend

Sources: [`frontend/src/routes/index.tsx`](../frontend/src/routes/index.tsx),
[`frontend/src/routes/production.tsx`](../frontend/src/routes/production.tsx),
[`frontend/src/routes/review.tsx`](../frontend/src/routes/review.tsx),
[`frontend/src/routes/completed.tsx`](../frontend/src/routes/completed.tsx),
[`frontend/src/routes/configuration.tsx`](../frontend/src/routes/configuration.tsx),
[`frontend/src/routes/production_.$jobId.tsx`](../frontend/src/routes/production_.$jobId.tsx),
[`frontend/src/components/Sidebar.tsx`](../frontend/src/components/Sidebar.tsx),
[`frontend/src/components/JobsPage.tsx`](../frontend/src/components/JobsPage.tsx),
[`frontend/src/components/NewVideoModal.tsx`](../frontend/src/components/NewVideoModal.tsx),
[`frontend/src/components/ModelPanel.tsx`](../frontend/src/components/ModelPanel.tsx),
[`frontend/src/components/ModelConfigModal.tsx`](../frontend/src/components/ModelConfigModal.tsx),
[`frontend/src/routes/series.tsx`](../frontend/src/routes/series.tsx),
[`frontend/src/routes/series_.$seriesId.tsx`](../frontend/src/routes/series_.$seriesId.tsx),
[`frontend/src/components/series/`](../frontend/src/components/series),
[`frontend/src/lib/api.ts`](../frontend/src/lib/api.ts),
[`frontend/src/lib/format.ts`](../frontend/src/lib/format.ts),
[`frontend/src/router.tsx`](../frontend/src/router.tsx).

## Responsibility

Operational dashboard: list jobs, create drafts, run/approve, inspect stages
and artifacts, show model cache/GPU. Thin client — no pipeline decisions.

## Public surface

Eight TanStack Router file routes:

- `/` (`routes/index.tsx`) — landing page. Sidebar (no tab highlighted) plus a
  centered welcome hero ("New video" CTA, opens `NewVideoModal`) and the
  `.stats` summary cards (total/in-production/ready-for-review). No job list.
  Polls `GET /api/jobs` every 1s, `/api/health` every 15s for the counts.
  Creating a video navigates to `/production/$jobId`.
- `/production`, `/review`, `/completed` (`routes/production.tsx`,
  `routes/review.tsx`, `routes/completed.tsx`) — each a thin wrapper around
  the shared `<JobsPage>` component (`components/JobsPage.tsx`), which owns
  the sidebar, header, section heading/count, job grid, and (for
  `/production` only) the "New video" button and a "Show completed" checkbox
  that hides `status === "completed"` jobs by default. `/review` filters to
  `awaiting_approval`, `/completed` to `completed`. Each job card is a `Link`
  to `/production/$jobId`.
- `/series` (`routes/series.tsx`) — series cards (name, description, video
  count, slug) and a "New series" modal that POSTs `/series` and navigates to
  the detail page. Sidebar tab `series`; shared chrome in
  `components/series/SeriesChrome.tsx` (`useWorkspace` polls `/jobs` 1s and
  `/health` 15s).
- `/series/$seriesId` (`routes/series_.$seriesId.tsx`, trailing underscore as
  for production detail) — heading with "New video" (opens `NewVideoModal`
  preset to the series) and "Delete series" (surfaces the 409 when videos
  still use it), plus tabs:
  **Bible** (`BibleTab` + `BibleFields`: voice, palette swatches, preferred
  components, image style, glossary as `Term: definition` lines; "Save new
  version" PUTs and invalidates `["jobs"]`), **Themes** (`ThemesTab`: cards
  and a modal with name, blurb, and the same guidance fields), **Ideas**
  (`IdeasTab`: backlog cards with Start video / Drop / Restore / Delete; the
  start modal takes library sources and an optional URL + excerpt, required
  in local mode when no library source is picked, then navigates to the new
  job), **Assets** (`AssetsTab`: raw-body upload via `apiUpload` with name and
  kind, image/audio/video previews via `assetUrl`, archive/restore, "Show
  archived"), **Sources** (`SourcesTab`: add/remove reusable excerpts), and
  **Videos** (jobs with `series_id`, theme and "bible changed" badges, and a
  stale-count note).
- `/configuration` (`routes/configuration.tsx`) — hosts `<ModelPanel />` full
  page (no longer a collapsible `<details>` — see below) under a
  "Configuration" heading, with the same sidebar chrome
  (`active="configuration"`).
- `/production/$jobId` (file `routes/production_.$jobId.tsx` — the trailing
  underscore on `production_` escapes TanStack Router's automatic layout
  nesting under `/production`, so this route is a standalone sibling, not a
  child needing `/production`'s component to render an `<Outlet/>`) — a
  distraction-free, sidebar-less detail page for one job (back link to
  `/production` only). Reads `Route.useParams().jobId`, queries the same
  `["jobs"]` cache key as the list pages (so no duplicate polling), and owns
  the Run/Retry/Restart/Approve actions and the per-stage `<details>` list.
  `configChanged`/`label` helpers live in `lib/format.ts`, shared across
  routes. `NewVideoModal` (`components/NewVideoModal.tsx`) is the shared
  "New video" form, used by both `/` and `/production`.

`VITE_API_URL` or `http://localhost:8091`.

Create form (`NewVideoModal`, used on `/`, `/production`, and the series
page): title, brief, optional series and theme selects (shown when series
exist), library-source checkboxes (`LibrarySourcePicker`) for the chosen
series, and an optional source URL+excerpt (required in the UI when health
`provider === "local"` and no library source is selected).

Job detail shows a series badge (series · theme · bible version, linking to
the series) and, when `series_stale`, a warning banner; `needsRestart`
(`lib/format.ts`) makes Restart the primary action for stale config or series.
For series jobs, narration WAV and generated images get a "Promote to series"
button (name via `window.prompt`) that POSTs
`/jobs/{id}/artifacts/{artifact_id}/promote` and shows the result inline.

`lib/api.ts` adds series types, `apiSend` (PUT/PATCH JSON), `apiUpload` (raw
file body), `assetUrl`, and flattens FastAPI validation errors into
`field: message` strings. Actions POST `/jobs/{id}/run`, `/restart` (clears
stages and rebases `config_hash`), `/approve`, and (via `submitManualResponse`,
typed by `ManualStageOutput`) `/jobs/{id}/stages/{stage}/manual-response`.
Narration download via `artifactUrl`. A job with `config_changes` shows a note that the pipeline
continues on the current models and which pending stages the latest change
affects; a job with `corrections` shows which stage sent it back and why.
`configChanged` (`lib/format.ts`) still matches legacy error text.

Manual stage input: when a stage is `awaiting_input` (job
`awaiting_manual_input` — a stage routed to `"manual"` in
[pipeline.md](../docs/pipeline.md#manual-routing-human-relay)), its
`<details>` panel shows the pasted-response round number, the composed
prompt (`stage.output.manual.prompt`) in a `<pre>` with a "Copy prompt"
button (`navigator.clipboard.writeText`), a paste-back `<textarea>`, and a
"Submit reply" button that POSTs `/jobs/{id}/stages/{stage}/manual-response`
via `submitManualResponse` (`lib/api.ts`) and invalidates `["jobs"]` on
success, clearing the draft. A 400 (malformed paste) surfaces through the
same shared error block as the other job actions; the job stays parked.

Delete: `apiDelete` (`lib/api.ts`) issues `DELETE /jobs/{id}` (no JSON body on
204 success). Available in two places, both gated by a `window.confirm`
naming the job title — any job status can be deleted, no state restriction:
a trash icon on each `JobsPage` job card (revealed on hover, `stopPropagation`
+ `preventDefault` so it doesn't trigger the card's `Link`) that invalidates
`["jobs"]` in place, and a "Delete pipeline" button in `production_.$jobId.tsx`'s
actions row that invalidates `["jobs"]` and navigates back to `/production`.

`ModelPanel` consumes `/api/models` (types `ModelStatus`, `ModelsResponse`,
`SetupState` in `lib/api.ts`), polling every 15s, or every 2s while
`setup_running`. Each card shows a badge (`downloading`, `installing`,
`setup failed`, `prepared`, `setup needed`, `optional · disabled`), the last
install log line, and actions: **Download weights** (hidden once cached),
**Install runtime** (hidden once installed; tooltip shows the `uv sync`
command), **Configure**, and **Reset** (only when `overridden`, with a
confirm). Actions POST `/models/{role}/download`, `/install-runtime`, and
`/config/reset`; errors render inline. `ModelConfigModal` edits the
overridable spec fields (repo, revision, filename, files one per line, device;
GPU layers/context/max tokens for `llama_cpp`; voice/speed for TTS; steps for
images) and POSTs only the changed fields to `/models/{role}/config`.

Vite: `127.0.0.1:3091`. pnpm (Corepack) scripts: `dev`, `build`, `typecheck`, `format`.

## How it is called

From the repo root, `make dev` starts the API (`uv run uvicorn` on `127.0.0.1:8091`) and `pnpm dev` together. `make dev-ui` (alias `make dashboard`) runs only the dashboard. CORS must include the Vite origin. Install with Corepack: `corepack enable && corepack prepare`, then `pnpm install --frozen-lockfile` in `frontend/`.

## Invariants

No tokens in localStorage or query strings. Commands only; worker owns state.

## Related tests

No frontend unit/e2e suite yet. Verify in a browser after UI changes.

## Known limitations

One inline source in the form vs API max 10 (library sources add more). No
auth. No generated OpenAPI types. Series pages poll jobs rather than using a
series-scoped query. No storyboard preview of `SeriesAsset` scenes.
