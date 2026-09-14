# Models (hub, GPU, runner, runtime, setup, CLI)

Sources: [`backend/app/models/hub.py`](../backend/app/models/hub.py),
[`gpu.py`](../backend/app/models/gpu.py),
[`runner.py`](../backend/app/models/runner.py),
[`runtime.py`](../backend/app/models/runtime.py),
[`fidelity.py`](../backend/app/models/fidelity.py),
[`setup.py`](../backend/app/models/setup.py),
[`cli.py`](../backend/app/models/cli.py).

## Responsibility

Download/pin Hugging Face snapshots, exclusive GPU queue, isolated inference
subprocesses, dashboard-triggered setup, operator CLI.

## Public surface

- `ModelHub.download` / `resolve` — commit pin, allow_patterns, atomic
  manifest. `extra_repos` are downloaded, pinned, and verified under
  `manifest["extras"][name]` (`repo_id`, `revision`, `snapshot`, `files`,
  `filename`). `ModelNotReady` if any snapshot is missing or incomplete.
- `GPUManager.acquire(resource, priority, timeout, metadata, unload)` —
  heap queue; one `active`; unload in `finally`.
- `LocalRunner.run(role, payload, job_id)` — spawn child with stripped env
  (no `HF_TOKEN`), pass `spec`, `snapshot`, `extras`, `payload`; wait; kill on
  timeout/cancel. A non-zero child without `result.json` raises using a
  token-scrubbed stderr tail (native abort / missing extra). The child writes
  JSON for Python failures, including a gone parent (`ORCHESTRATOR_PARENT_PID`).
- `runtime.infer(spec, snapshot, payload, extras)` — child entry point.
  - `llama_cpp`: payload `{"requests": [{"messages", "schema_name", "seed"?,
    "temperature"?}]}` → `{"results": [{"result", "repaired"} |
    {"error", "kind": "validation"}]}`. **One `Llama` construction per child**;
    each request is grammar-constrained to the pydantic schema named in
    `app.schemas`, validated in the child, and re-prompted **once** before the
    item is reported as an error. A validation error is repaired by replaying
    the output with the error. Output cut off at `max_tokens`
    (`finish_reason: length`, usually a repetition loop) raises
    `OutputTruncated`; the retry is **not** shown the truncated text — it
    restarts from the original messages plus a "be concise" instruction, with
    `seed + 1` and `repeat_penalty: 1.1`. The grammar is built from
    `grammar_schema(...)`, which keeps `minLength` / `maxLength` up to 1000 and
    `maxItems` up to 30 (`GRAMMAR_BOUND_LIMITS`) and drops larger values:
    llama.cpp unrolls those bounds into nested repetition groups, and a
    `maxLength` of 2000 already fails to compile and aborts the child. Kept
    bounds stop runaway lists and strings during decoding (e.g. `Critic` lists
    of at most 6 items of 300 chars); dropped bounds are enforced by pydantic
    validation only. `Script.text`, `Research.summary`, `Metadata.description`,
    and critic items reject leaked reasoning (`schemas.REASONING_LEAK`: think
    tags, "Okay, let me…"/"First, I…" openers, "the user provided…" in the
    first 300 chars), so it goes through the repair pass instead of becoming
    output. Inclusive narrator openers ("So, let's…") are not flagged.
    `think_toggle` is appended to the system message here. When it is set and
    the GGUF chat template references `enable_thinking` (Qwen3), the child also
    renders that template with `enable_thinking=False`, which pre-fills an empty
    `<think></think>` block: under a JSON grammar Qwen3 otherwise ignores
    `/no_think` and writes its reasoning into the first string field (e.g.
    `Script.text`). `n_gpu_layers` is honoured for `cuda` and `metal`.
  - `kokoro` / `qwen_tts`: sentence-chunked WAV, `{duration_seconds,
    sample_rate, segments, voice, speed}`. `metal` maps to torch `mps`.
  - `whisper`: transcript segments/words plus `method: asr_transcript` and
    `fidelity = 1 − WER(script, transcript)` when the payload carries `text`.
  - `ctc_aligner`: forced alignment of the known `text`; segments regrouped
    into script sentences; `method: forced_alignment`; `fidelity =
    exp(mean word log-probability)`.
  - `sentence_transformers`: normalised embeddings on CPU.
  - `diffusers` (SDXL) / `diffusers_gguf` (FLUX.1-schnell GGUF transformer +
    GGUF T5 encoder, CPU offload, `steps`, guidance 0): 768×768 PNG, CUDA only.
- `fidelity.word_error_rate` / `fidelity` — pure-Python word-level Levenshtein.
- `SetupManager(hub, root, command_factory)` — in-process background setup
  for the dashboard. One `SetupTask` per key: `download:<role>` runs
  `ModelHub.download` in a thread; `install:<extra>` runs the fixed
  `uv sync --extra <extra>` subprocess in `backend/` with `HF_TOKEN` stripped
  and `importlib.invalidate_caches()` on success. States `idle → running →
  done | failed`, `started_at`/`ended_at`, `error`, and a 50-line log tail.
  `start_*` raises `SetupBusy` while the same key is running; `start_install`
  raises `ValueError` unless the extra is a value of `RUNTIME_EXTRAS`.
  `scrub()` replaces the `HF_TOKEN` value and `hf_…` tokens with `***` in
  logs and errors. `status(key)`, `is_running(key)`, `any_running()`.
- CLI: `python -m app.models.cli list | download ROLE | download all`
  (`all` skips the disabled image role; `list` marks roles with a dashboard
  override as `(overridden)`).

## How it is called

LocalProvider → LocalRunner → GPU lock → runtime adapters. Dashboard
`GET /api/models` reports cache, setup state, and `gpu.status()`;
`POST /api/models/{role}/download` and `/install-runtime` start
`SetupManager` tasks (see [api.md](api.md)).

## Invariants

Priority: lower number first. Unload always. Timeouts cancel waiters and
children. File lock on cache manifests. Embeddings CPU-only (config). A
validation error after the repair pass is a `RuntimeError` in the parent, so
the worker's bounded retry applies.

## Related tests

`test_models.py` (including `test_setup_manager_scrubs_token_and_rejects_unknown_extra`,
`test_setup_manager_download_states`), `test_runtime.py`, and the
`/api/models` tests in `test_local_api.py`.

## Known limitations

Setup state is held in the API process: a restart forgets running or failed
tasks (the cache manifest still records finished downloads) and there is no
cancel. Runtime installs modify the shared `.venv`, so they are not
serialised against running inference children. Unrelated GPU processes are
not preempted. Real library behaviour (llama.cpp,
Kokoro, Qwen3-TTS, diffusers) is exercised only with fakes in the suite.
