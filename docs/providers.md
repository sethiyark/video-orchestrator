# Providers

Source: [`backend/app/providers.py`](../backend/app/providers.py).

## Responsibility

Stable `Provider.execute(stage, job, attempt=0) -> dict` so the worker does not
care whether the backend is mock or local.

## Public surface

`STAGES` list (order is the pipeline). `MockProvider` sleeps then returns
placeholder JSON: no audio, no embeddings, no video, upload message states
nothing was sent to YouTube.

## How it is called

`create_app` picks `LocalProvider` if `settings.mode == "local"` else
`MockProvider`. Tests inject fakes.

## Invariants

Worker retries: local uses `models.governor.max_attempts`; mock is 1 attempt
(manual retry). Mock failures stay manual. `run_stages` (`backend/app/main.py`)
passes the 0-based retry index as `attempt` on every call, including the
first. `LocalProvider` uses it to offset the default LLM seed
(`42 + attempt + correction attempt`, and `42 + attempt * len(CRITICS) + index` for the five
parallel critics) so a worker-level retry does not just replay the previous
attempt's request byte-for-byte: local inference is deterministic given a
fixed seed and prompt, so an unvaried retry of a validation failure (e.g. a
storyboard scene violating `MAX_SCENE_SENTENCES`) reproduces the identical bad
output every time instead of giving the model an actual second chance. A
request-level `seed` passed through `llm_batch`'s `options` still overrides
the default.

Rewinds (local only): when a stage's final attempt raises `ReviewRequired`
with `rewind_to` set to the same or an earlier stage, `create_app`'s `rewind` resets
every stage from the target onward to `pending` (outputs
cleared), stores `job["corrections"][target] = {from_stage, attempt, message,
**details}`, increments `job["rewinds"][failed_stage]`, and `run_stages`
starts again from the first incomplete stage. Each failed attempt is still
recorded in `stage_attempts`. Once `rewinds[failed_stage]` reaches
`governor.max_rewinds` the error propagates and the job fails for human
review as before. A correction is deleted when the stage that raised it
completes. `/restart` clears `rewinds` and `corrections`; `/run` (retry)
keeps them, so a job that used its budget stays manual until restarted.
Mock mode never rewinds.

Config changes (local only): `rebase_config` runs at `/run` and before every
stage. If `provider.config_hash` differs from the job's, it appends
`{at, previous, current, pending_stages_affected}` to `job["config_changes"]`
(affected = pending stages whose `provider.stage_hashes` entry differs from the
job's stored `stage_hashes`; all pending stages when the job predates
`stage_hashes`), stamps the live hashes, logs, and continues. The pipeline is
never refused for a config change; a model that cannot load fails its own
stage with `ModelNotReady`, and the operator can `/restart` for a clean run.

Manual routing (local only): `LocalProvider.llm_batch` raises
`ManualStepRequired(prompt, schema_names)` instead of calling `LocalRunner`
when `config.routes[stage] == "manual"` and no pasted response is cached yet
for that call ([pipeline.md](pipeline.md)). `run_stages` catches it before
the generic retry/rewind handling — like the `upload`/`awaiting_approval`
gate, it returns `"waiting"` without marking the attempt failed or the stage
`failed`, setting the job to `awaiting_manual_input` and the stage to
`awaiting_input`. No `GPUManager`/`LocalRunner` call happens for a manual
call, so it never touches the GPU queue.

## Related tests

`test_pipeline.py` (mock worker; `test_failed_stage_rewinds_with_corrections_and_continues`,
`test_rewind_budget_is_bounded_then_requires_review`, `test_mock_mode_never_rewinds`, `test_config_change_mid_run_is_recorded_not_blocking`).
`test_local_api.py::test_manual_script_stage_parks_and_resumes_via_api` (manual routing end to end).

## Known limitations

Mock completion is not a real video. Do not treat mock outputs as evidence.
