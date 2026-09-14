# Local models and GPU

Sources: [`backend/config/models.yaml`](../backend/config/models.yaml),
[`models.mac.yaml`](../backend/config/models.mac.yaml),
[`models.cuda-8gb.yaml`](../backend/config/models.cuda-8gb.yaml),
[`backend/app/models/`](../backend/app/models/), [models.md](models.md).

## Responsibility

Fit the pipeline on **16 GB RAM + 8 GB VRAM** (CUDA host) and on Apple Silicon
(Metal) for development. Throughput over latency: load → run many requests →
unload. **Do not** keep FAST and QUALITY GGUF models plus a diffusion
checkpoint resident.

## Public surface

| Role | Default (`models.yaml`) | Runtime | Device | Resident size (approx) |
| --- | --- | --- | --- | --- |
| `fast` | `Qwen/Qwen3-4B-GGUF` Q4_K_M | llama.cpp | cpu / metal / cuda | 2.5 GB |
| `quality` | `Qwen/Qwen3-8B-GGUF` Q4_K_M (opt-in comment: `unsloth/Qwen3.5-9B-GGUF`, text-only) | llama.cpp | cpu / metal / cuda | 5 GB + ~2.4 GB KV at 16k (CUDA profile: 12k, ~1.8 GB) |
| `narration` | `hexgrad/Kokoro-82M` (`kokoro`); CUDA profile: `Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice` (`qwen_tts`, `speaker: Ryan`) | Kokoro / Qwen3-TTS | cpu / metal / cuda | <0.5 GB / ~2 GB |
| `alignment` | `deepdml/faster-whisper-large-v3-turbo-ct2` int8 (`whisper`); CUDA profile: `MahmoudAshraf/mms-300m-1130-forced-aligner` (`ctc_aligner`) | faster-whisper / ctc-forced-aligner | cpu / cuda | ~1.6 GB / ~1.2 GB |
| `embeddings` | `Qwen/Qwen3-Embedding-0.6B` | sentence-transformers | **CPU only** | ~1.2 GB |
| `images` | CUDA: `city96/FLUX.1-schnell-gguf` Q4_K_S + GGUF T5 + FLUX base. Mac: `stabilityai/sdxl-turbo` | `diffusers_gguf` / `diffusers` | **cuda** (FLUX GGUF) or **metal** (SDXL-Turbo); off in default `models.yaml`. Only used when `routes.assets: images`; the shipped profiles route `assets` to `manual` (image relay) so no image model is needed | ~6.8 GB FLUX or ~5 GB Turbo |

Peak memory is one GGUF plus its KV cache because `GPUManager` serialises all
inference. The Mac profile uses the SDXL `diffusers` runtime on MPS; FLUX GGUF
stays on the CUDA profile.

Profiles (select with `MODEL_CONFIG`):

- `models.yaml` — CPU-portable; tests load it.
- `models.mac.yaml` — `device: metal`, `gpu_layers: -1` for both GGUF roles,
  Kokoro on MPS, `images_enabled: true` with SDXL-Turbo on MPS.
  `make dev-local-mac` starts the local API and dashboard together.
- `models.cuda-8gb.yaml` — `device: cuda`, `gpu_layers: -1`, Qwen3-TTS,
  CTC forced aligner, `images_enabled: true`. `make dev-local-cuda` starts
  the local API and dashboard together.

`ModelSpec` fields beyond the repo: `device` (`cpu|cuda|metal`),
`context_size`, `max_tokens`, `gpu_layers`, `think_toggle` (appended to the
system prompt by the child, which also renders a template that supports
`enable_thinking` with it off; `/no_think` for Qwen3/SmolLM3, `null` to disable),
`voice` (Kokoro), `speaker` (Qwen3-TTS), `speed`, `steps` (images),
`extra_repos` (companion snapshots pinned in the same manifest), `priority`,
`timeout_seconds`.

## How it is called

1. Pick a profile or edit YAML (repo_id, revision, files, device, gpu_layers),
   or use **Configure** on a Model library card: the change is saved to the
   overlay file (`MODEL_OVERLAY`, default `backend/data/models.local.yaml`)
   and merged over the profile. **Reset** removes it.
2. `MODEL_CONFIG=… python -m app.models.cli download ROLE` (or `all`), or
   click **Download weights** / **Install runtime** on the card. Installs run
   `uv sync --extra <extra>` in `backend/` and can take minutes.
3. Existing jobs keep going on the new configuration: the change is recorded
   on the job (`config_changes`, with the pending stages it affects) and shown
   on the job page. **Restart** a draft/failed/awaiting/completed job only
   when you want every stage regenerated with the current models.

Metal needs the Metal wheel of `llama-cpp-python` (README). Whisper and the
CTC aligner run on CPU or CUDA only. SDXL (`diffusers`) runs on MPS; FLUX
GGUF (`diffusers_gguf`) does not.

## Invariants

Lower GPU `priority` number runs first. Timeouts cancel waiters. Unload hooks
always run. Status on `GET /api/models`. Cache directory file lock plus one
worker per database. `metal` is accepted for `llama_cpp`, `kokoro`,
`qwen_tts`, and `diffusers`. `diffusers_gguf` requires `cuda`. Embeddings stay
on CPU.

## Related tests

`test_device_and_runtime_rules`, `test_hardware_profiles_validate`,
`test_sdxl_runs_on_metal`,
`test_hub_downloads_and_verifies_extra_repos`,
`test_gpu_priority_timeout_cancellation_and_cleanup`,
`test_runner_kills_child_on_timeout_and_releases_lock`.

## Known limitations

VRAM/RSS fit must be measured on the target GPU; drop the FLUX transformer to
Q3_K_S if 16 GB RAM is short during CPU offload. Qwen3.5 GGUFs load with the pinned
`llama-cpp-python>=0.3.35`, but their quality on this pipeline is unmeasured. ComfyUI is not connected.
