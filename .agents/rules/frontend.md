---
description: React/TypeScript operational dashboard
paths: frontend/**/*.ts,frontend/**/*.tsx,frontend/**/*.css,frontend/**/*.js,frontend/**/*.json
---

# Frontend (React / TypeScript)

Canonical file: `.agents/rules/frontend.md`. The UI lives in `frontend/`: Vite,
TanStack Start / Router / Query, **npm**. Document it in `docs/frontend.md`
and keep that file updated in the same change.

- React function components and hooks; TypeScript as in the existing sources.
- Keep it a thin client: pipeline, GPU scheduling, and persistence live in
  Python. The UI polls `/api/jobs` and `/api/health` and issues run/approve.
- Never put API keys, `HF_TOKEN`, or YouTube credentials in client code, local
  storage, or URLs.
- Verify UI work in a browser end to end — click, type, navigate the flows you
  touched. A single screenshot is not verification.
- After UI changes: `npm run typecheck` and `npm run build` from `frontend/`.
