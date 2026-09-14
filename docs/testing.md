# Testing

Source: [`backend/tests/`](../backend/tests).

## Responsibility

pytest from `backend/` (`pythonpath = ["."]`). Default suite needs no GPU,
no Hugging Face download, no live Temporal.

## Public surface

| File | Owns |
| --- | --- |
| `test_pipeline.py` | Mock worker, approval, retry, restart, interrupt recovery, retry attempt index reaches the provider, bounded same-stage validation rewinds |
| `test_local_provider.py` | Grounding (per-source research, tolerant quote location, quote retry), critics (script-only input), storyboard schema and sentence chunks, unverified claims, per-section script chunks and short-section retry, retry-attempt seed offset, alignment repair with TTS timing and narration rewinds |
| `test_local_api.py` | Local artifacts, render boundary, config-hash restart |
| `test_rendering.py` | Alignment timing, media validation, subprocess failures and MP4 adoption |
| `test_models.py` | Config/device rules, profiles, hub pin + extras, GPU queue, runner kill, child stderr on abort |
| `test_runtime.py` | Inference child with fake llama.cpp/whisper: batch, repair, truncation retry, leaked-reasoning rejection, grammar bounds, Metal layers, fidelity, WER, parent-pid JSON |
| `test_database.py` | Legacy import, locks; Postgres if `TEST_DATABASE_URL` |
| `test_control_plane.py` | Governor, scoring, states, health, object store |
| `test_series.py` | Series CRUD, bible versions, snapshot staleness, ideas, prompt guidance, uploads, library sources, promotion, `SeriesAsset` pinning |

Fakes: controlled model JSON (`FakeRunner` answers `requests` batches), fake
runtime processes, and fake heavy libraries injected into `sys.modules`.

## How it is called

```bash
cd backend
uv run pytest
uv run ruff check app tests migrations
```

Frontend: `pnpm typecheck` / `pnpm build` (not pytest).

## Invariants

Tests never hit the network or download weights. Do not skip lock or
approval tests to land a change.

## Known limitations

No Playwright. MinIO/Temporal/Postgres not required in default CI. Real model
quality is out of band on the GPU host.
