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
[`frontend/src/lib/api.ts`](../frontend/src/lib/api.ts),
[`frontend/src/lib/format.ts`](../frontend/src/lib/format.ts),
[`frontend/src/router.tsx`](../frontend/src/router.tsx).

## Responsibility

Operational dashboard: list jobs, create drafts, run/approve, inspect stages
and artifacts, show model cache/GPU. Thin client — no pipeline decisions.

## Public surface

Six TanStack Router file routes:

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

Create form (`NewVideoModal`, used on `/` and `/production`): title, brief,
optional source URL+excerpt (required in the UI when health
`provider === "local"`). Actions POST `/jobs/{id}/run`, `/restart` (clears
stages and rebases `config_hash`), and `/approve`. Narration download via
`artifactUrl`. When the job error mentions model configuration, Restart is
the primary action.

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

One source in the form vs API max 10. No auth. No generated OpenAPI types.
