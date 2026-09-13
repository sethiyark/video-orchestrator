# Frontend

Sources: [`frontend/src/routes/index.tsx`](../frontend/src/routes/index.tsx),
[`frontend/src/routes/configuration.tsx`](../frontend/src/routes/configuration.tsx),
[`frontend/src/routes/production.$jobId.tsx`](../frontend/src/routes/production.$jobId.tsx),
[`frontend/src/components/Sidebar.tsx`](../frontend/src/components/Sidebar.tsx),
[`frontend/src/components/ModelPanel.tsx`](../frontend/src/components/ModelPanel.tsx),
[`frontend/src/components/ModelConfigModal.tsx`](../frontend/src/components/ModelConfigModal.tsx),
[`frontend/src/lib/api.ts`](../frontend/src/lib/api.ts),
[`frontend/src/lib/format.ts`](../frontend/src/lib/format.ts),
[`frontend/src/router.tsx`](../frontend/src/router.tsx).

## Responsibility

Operational dashboard: list jobs, create drafts, run/approve, inspect stages
and artifacts, show model cache/GPU. Thin client — no pipeline decisions.

## Public surface

Three TanStack Router file routes, sharing a `Sidebar` component
(`active` tab, review-queue count, health) for the two list-style pages:

- `/` (`routes/index.tsx`) — the production dashboard: stats, the job list,
  and the "New video" form. Polls `GET /api/jobs` every 1s, `/api/health`
  every 15s. The sidebar's Production/Review queue/Completed tabs switch a
  local `filter` state in place (no navigation); the Configuration tab
  navigates to `/configuration`. On the `all` filter, jobs with
  `status === "completed"` are hidden by default behind a "Show completed"
  checkbox (`showCompleted` state) — the Review queue and Completed tabs are
  unaffected. Each job card is a `Link` to `/production/$jobId` (no more
  inline expansion on this page).
- `/configuration` (`routes/configuration.tsx`) — hosts `<ModelPanel />`
  (moved out of `/`) under a "Configuration" heading, with the same sidebar
  chrome (`active="configuration"`).
- `/production/$jobId` (`routes/production.$jobId.tsx`) — a distraction-free,
  sidebar-less detail page for one job (back link only). Reads `Route.useParams().jobId`,
  queries the same `["jobs"]` cache key as `/` (so no duplicate polling), and
  owns the Run/Retry/Restart/Approve actions and the per-stage `<details>`
  list that used to live inline on `/`. `configChanged`/`label` helpers live
  in `lib/format.ts`, shared with `/`.

`VITE_API_URL` or `http://localhost:8091`.

Create form (on `/`): title, brief, optional source URL+excerpt (required in
the UI when health `provider === "local"`). Actions POST `/jobs/{id}/run`,
`/restart` (clears stages and rebases `config_hash`), and `/approve`.
Narration download via `artifactUrl`. When the job error mentions model
configuration, Restart is the primary action.

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
