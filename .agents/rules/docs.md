---
description: Shared agent contract — follow AGENTS.md and keep docs/ in sync with the code
---

# Project contract

`AGENTS.md` is the shared guide for Cursor, Codex, and Claude Code. Read it
before editing, and follow its Working agreement, Documentation, and Invariants
sections. The bullets below are the parts easiest to forget.

This directory is the canonical rule pack. Cursor loads
[`.cursor/rules/`](../../.cursor/rules/); Claude Code loads
[`.claude/rules/`](../../.claude/rules/) (symlinks here). Codex also loads
nested `AGENTS.md` files in `backend/`, `backend/tests/`,
`backend/migrations/`, `frontend/`, and `docs/`.

- `docs/` is the module-by-module implementation reference. Any change to
  behaviour, a public interface, a config key, a schema, or an invariant
  updates the matching `docs/` file in the same change.
- A new module gets `docs/<module>.md` plus a row in `docs/README.md`.
- Docs describe what exists today: the in-process FastAPI worker, SQLite or
  PostgreSQL job tables, mock/local providers, GPU queue, and the Temporal
  **health** canary. [`docs/IMPLEMENTATION_PLAN.md`](../../docs/IMPLEMENTATION_PLAN.md)
  is the roadmap — never document unbuilt phases as current, and do not
  implement from the plan unless asked.
- Do not create new top-level markdown or summary files. Extend `README.md`,
  `docs/`, `AGENTS.md`, or `.agents/rules/`. After changing a scoped rule, keep
  the Cursor `.mdc` mirror in `.cursor/rules/` aligned.
- Upload requires `approved_at`. Local mode must not invent an MP4 or call
  YouTube. `autonomous_publish` stays false unless the user explicitly asks.
- Logical agents never execute LLM-generated shell or code. Scene JSON is
  schema-validated. The Channel Governor is not mutable by agents.
- Exclusive GPU lock: do not load FAST and QUALITY GGUF plus a diffusion
  checkpoint at once. Unload hooks must still run on failure.
- Never commit or print secrets (`.env`, `HF_TOKEN`, YouTube OAuth, MinIO
  production passwords). Never commit unless asked.
