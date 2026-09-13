# Local models and GPU

Sources: [`backend/config/models.yaml`](../backend/config/models.yaml),
[`backend/app/models/`](../backend/app/models/), [models.md](models.md).

## Responsibility

8 GB VRAM policy and logical roles. **Do not** keep FAST and QUALITY GGUF
models plus a diffusion checkpoint resident. Throughput over latency: load →
run → unload.

## Public surface

| Role | Default example | Runtime | Device default |
| --- | --- | --- | --- |
| `fast` | SmolLM3 3B Q4 GGUF | llama.cpp (in-process subprocess today) | CPU portable; CUDA on host |
| `quality` | Qwen3 8B Q4 GGUF | llama.cpp | CPU portable; CUDA on host |
| `narration` | Kokoro-82M | Kokoro | CPU |
| `alignment` | faster-whisper small | Whisper | CPU |
| `embeddings` | all-MiniLM-L6-v2 | sentence-transformers | **CPU only** |
| `images` | SDXL FP16 | diffusers | CUDA, **disabled** by default |

Stage routes in YAML select a role. Hugging Face is download-only; inference
uses prepared snapshots with offline mode.

**Now:** `llama-cpp-python` in an isolated subprocess per call (`LocalRunner`).
Exclusive GPU lock around the subprocess. Weights via
`python -m app.models.cli download`.

**Not built:** HTTP llama.cpp / Ollama `ModelProvider`, external LLM
escalation (Governor flag exists, default off).

## How it is called

1. Edit YAML (repo_id, revision, files, device, gpu_layers).
2. `python -m app.models.cli download ROLE`
3. Create a **new** draft (`config_hash` is stored on the job).

## Invariants

Lower GPU `priority` number runs first. Timeouts cancel waiters. Unload hooks
always run. Status on `GET /api/models`. Cache directory file lock plus one
worker per database. Unrelated processes (hand-started ComfyUI) are outside
this scheduler.

## Related tests

`test_gpu_priority_timeout_cancellation_and_cleanup`,
`test_runner_kills_child_on_timeout_and_releases_lock`,
`test_hub_pins_commit_and_detects_missing_cache`.

## Known limitations

VRAM fit must be measured on the target GPU. Default YAML is CPU for
portability. ComfyUI is not connected.
