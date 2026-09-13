# Models (hub, GPU, runner, CLI)

Sources: [`backend/app/models/hub.py`](../backend/app/models/hub.py),
[`gpu.py`](../backend/app/models/gpu.py),
[`runner.py`](../backend/app/models/runner.py),
[`cli.py`](../backend/app/models/cli.py),
[`runtime.py`](../backend/app/models/runtime.py).

## Responsibility

Download/pin Hugging Face snapshots, exclusive GPU queue, isolated inference
subprocesses, operator CLI.

## Public surface

- `ModelHub.download` / `resolve` — commit pin, allow_patterns, atomic
  manifest. `ModelNotReady` if cache missing.
- `GPUManager.acquire(resource, priority, timeout, metadata, unload)` —
  heap queue; one `active`; unload in `finally`.
- `LocalRunner.run` — spawn child with stripped env (no `HF_TOKEN` in child),
  wait, kill on timeout/cancel.
- CLI: `python -m app.models.cli list | download ROLE | download all`
  (`all` skips disabled image role).

## How it is called

LocalProvider → LocalRunner → GPU lock → runtime adapters. Dashboard
`GET /api/models` reports cache + `gpu.status()`.

## Invariants

Priority: lower number first. Unload always. Timeouts cancel waiters and
children. File lock on cache manifests. Embeddings CPU-only (config).

## Related tests

`test_models.py`.

## Known limitations

Unrelated GPU processes are not preempted. Hard-kill of children on non-Linux
is not guaranteed. HTTP llama.cpp server is not wired.
