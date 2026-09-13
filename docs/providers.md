# Providers

Source: [`backend/app/providers.py`](../backend/app/providers.py).

## Responsibility

Stable `Provider.execute(stage, job) -> dict` so the worker does not care
whether the backend is mock or local.

## Public surface

`STAGES` list (order is the pipeline). `MockProvider` sleeps then returns
placeholder JSON: no audio, no embeddings, no video, upload message states
nothing was sent to YouTube.

## How it is called

`create_app` picks `LocalProvider` if `settings.mode == "local"` else
`MockProvider`. Tests inject fakes.

## Invariants

Worker retries: local uses `models.governor.max_attempts`; mock is 1 attempt
(manual retry). Mock failures stay manual.

## Related tests

`test_pipeline.py` (mock worker).

## Known limitations

Mock completion is not a real video. Do not treat mock outputs as evidence.
