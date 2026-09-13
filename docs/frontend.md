# Frontend

Sources: [`frontend/src/routes/index.tsx`](../frontend/src/routes/index.tsx),
[`frontend/src/components/ModelPanel.tsx`](../frontend/src/components/ModelPanel.tsx),
[`frontend/src/lib/api.ts`](../frontend/src/lib/api.ts),
[`frontend/src/router.tsx`](../frontend/src/router.tsx).

## Responsibility

Operational dashboard: list jobs, create drafts, run/approve, inspect stages
and artifacts, show model cache/GPU. Thin client — no pipeline decisions.

## Public surface

Single route `/` (TanStack Router file route). Polls `GET /api/jobs` every 1s,
`/api/health` every 15s. `VITE_API_URL` or `http://localhost:8091`.

Create form: title, brief, optional source URL+excerpt (required in the UI
when health `provider === "local"`). Actions POST `/jobs/{id}/run` and
`/approve`. Narration download via `artifactUrl`.

`ModelPanel` consumes `/api/models`.

Vite: `127.0.0.1:3091`. pnpm (Corepack) scripts: `dev`, `build`, `typecheck`, `format`.

## How it is called

From the repo root, `make dev` starts the API (`uv run uvicorn` on `127.0.0.1:8091`) and `pnpm dev` together. `make dev-ui` (alias `make dashboard`) runs only the dashboard. CORS must include the Vite origin. Install with Corepack: `corepack enable && corepack prepare`, then `pnpm install --frozen-lockfile` in `frontend/`.

## Invariants

No tokens in localStorage or query strings. Commands only; worker owns state.

## Related tests

No frontend unit/e2e suite yet. Verify in a browser after UI changes.

## Known limitations

One source in the form vs API max 10. No auth. No generated OpenAPI types.
