---
description: Python conventions for the FastAPI pipeline
paths: backend/**/*.py,backend/tests/**/*.py,backend/migrations/**/*.py
---

# Python

Canonical file: `.agents/rules/python.md`. Full project rules are in
`AGENTS.md`; module detail is in `docs/`.

- **`backend/app/`** — FastAPI modular monolith: API, in-process worker,
  providers, models, persistence. Verify with `uv run pytest` and
  `uv run ruff check app tests migrations` from `backend/`.
- Python >= 3.12, managed with **uv**. Optional extras: `llm`, `audio`,
  `embeddings`, `images`. Do not add those to the default install unless the
  change needs them.
- `from __future__ import annotations` where existing files use it. PEP 604
  unions (`str | None`).
- `log = logging.getLogger(__name__)`. No `print()` except
  [`app/database.py`](../../backend/app/database.py) `__main__` and CLI
  helpers. `CRITICAL` is for things a human must act on now.
- New Python deps via uv / [`backend/pyproject.toml`](../../backend/pyproject.toml).
- Do not execute LLM-generated code or shell. Do not fetch source URLs in the
  research path (excerpts are supplied). Do not fake render/upload success.
- Update the matching `docs/` file in the same change as any behaviour, API,
  schema, or invariant change.
