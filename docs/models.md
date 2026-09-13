# Models (hub, GPU, runner, runtime, CLI)

Sources: [`backend/app/models/hub.py`](../backend/app/models/hub.py),
[`gpu.py`](../backend/app/models/gpu.py),
[`runner.py`](../backend/app/models/runner.py),
[`runtime.py`](../backend/app/models/runtime.py),
[`fidelity.py`](../backend/app/models/fidelity.py),
[`cli.py`](../backend/app/models/cli.py).

## Responsibility

Download/pin Hugging Face snapshots, exclusive GPU queue, isolated inference
subprocesses, operator CLI.

## Public surface

- `ModelHub.download` / `resolve` — commit pin, allow_patterns, atomic
  manifest. `extra_repos` are downloaded, pinned, and verified under
  `manifest["extras"][name]` (`repo_id`, `revision`, `snapshot`, `files`,
  `filename`). `ModelNotReady` if any snapshot is missing or incomplete.
- `GPUManager.acquire(resource, priority, timeout, metadata, unload)` —
  heap queue; one `active`; unload in `finally`.
- `LocalRunner.run(role, payload, job_id)` — spawn child with stripped env
  (no `HF_TOKEN`), pass `spec`, `snapshot`, `extras`, `payload`; wait; kill on
  timeout/cancel.
- `runtime.infer(spec, snapshot, payload, extras)` — child entry point.
  - `llama_cpp`: payload `{"requests": [{"messages", "schema_name", "seed"?,
    "temperature"?}]}` → `{"results": [{"result", "repaired"} |
    {"error", "kind": "validation"}]}`. **One `Llama` construction per child**;
    each request is grammar-constrained to the pydantic schema named in
    `app.schemas`, validated in the child, and re-prompted **once** with the
    validation error before the item is reported as an error.
    `think_toggle` is appended to the system message here. `n_gpu_layers` is
    honoured for `cuda` and `metal`.
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
- CLI: `python -m app.models.cli list | download ROLE | download all`
  (`all` skips the disabled image role).

## How it is called

LocalProvider → LocalRunner → GPU lock → runtime adapters. Dashboard
`GET /api/models` reports cache + `gpu.status()`.

## Invariants

Priority: lower number first. Unload always. Timeouts cancel waiters and
children. File lock on cache manifests. Embeddings CPU-only (config). A
validation error after the repair pass is a `RuntimeError` in the parent, so
the worker's bounded retry applies.

## Related tests

`test_models.py`, `test_runtime.py`.

## Known limitations

Unrelated GPU processes are not preempted. Real library behaviour (llama.cpp,
Kokoro, Qwen3-TTS, diffusers) is exercised only with fakes in the suite.
