# Orchestrator (Temporal)

Sources: [`backend/app/orchestrator/workflows.py`](../backend/app/orchestrator/workflows.py),
[`worker.py`](../backend/app/orchestrator/worker.py),
[`client.py`](../backend/app/orchestrator/client.py).

## Responsibility

Temporal **health canary** only. Does not generate video content.

## Public surface

`HealthWorkflow.run(ping="ok") -> str`. Task queue `video-orchestrator`.
`check_temporal(target)` → `"disabled"` if unset, else connect with 2s timeout.
Worker `python -m app.orchestrator.worker` requires `TEMPORAL_TARGET`.

Compose runs this worker beside the API.

## How it is called

Health endpoint probes Temporal. Worker process is separate from the
in-process job loop.

## Invariants

Do not register a video production workflow here and claim it is live without
tests and docs. Video execution remains `Store` + `Provider`.

## Related tests

Health path in `test_health_and_system_and_metrics` (Temporal typically
`disabled` in unit tests).

## Known limitations

No `VideoProductionWorkflow`, no activity retries for research-to-script, no
idempotent YouTube upload workflow.
