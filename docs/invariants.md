# Invariants

Cross-cutting rules. Weaken these only with an explicit product decision and
tests.

## GPU and processes

- Only one GPU-heavy workload via `GPUManager.acquire` (CUDA or Metal). Unload
  hooks run even on failure. A child may answer several requests, but loads
  one model.
- Do not load FAST and QUALITY GGUF plus diffusion at once.
- Embeddings stay on CPU.
- One model worker per database (advisory lock or SQLite file lock).
  `RUN_WORKER=false` for extra API processes.
- Inference children and runtime-install subprocesses do not inherit
  `HF_TOKEN`.
- The only install the API runs is `uv sync --extra <extra>` with an extra
  from `RUNTIME_EXTRAS`. Dashboard overrides are validated as a full
  `ModelConfig` before they are written and can only touch
  `OVERRIDABLE_FIELDS`.

## Publish and Governor

- Upload stage requires `approved_at`.
- `autonomous_publish` defaults to false. Agents cannot mutate Governor YAML
  at runtime.
- Local `render` / `upload` must not invent success. Mock may label outputs
  as simulated.

## Evidence and tools

- Local jobs require source excerpts. URLs are not fetched.
- Fabricated quotes and unverified-claim scripts fail closed. Quote matching
  tolerates flattened punctuation, whitespace, and case, never changed words;
  stored quotes are the excerpt's exact text.
- Narration whose alignment fidelity is below `min_narration_fidelity` fails
  closed; alignment always receives the script text.
- Inputs over the route's context budget fail closed before a model load.
- Storyboard components are a closed enum; no LLM shell/code execution.
  `SeriesAsset` references an existing active series image/logo by id only.
- Scripts, and each script section, far shorter than their outline fail
  closed; one targeted retry batch runs first.
- Storyboard scenes reference script sentences; narration text is copied by
  the provider.
- Series bibles, themes, and glossaries are style data, never evidence. A job
  snapshots them at creation; a changed bible/theme blocks `/run` until
  Restart rebinds the snapshot. Library sources are copied into jobs, never
  referenced ([series.md](series.md)).
- Series uploads accept only allowlisted media whose bytes match the declared
  type (no SVG/HTML) and are served as attachments.
- Writer/research tool allowlists: see [logical-agents.md](logical-agents.md).

## HTTP and secrets

- Development binds loopback. No dashboard auth — treat the API as
  trusted-host.
- Secrets only from the environment. Never log or persist tokens.

## Docs

Behaviour, API, config, schema, and invariant changes update `docs/` in the
same change.

## Owning tests

`test_pipeline.py`, `test_local_provider.py`, `test_local_api.py`,
`test_models.py`, `test_runtime.py`, `test_database.py`, `test_control_plane.py`,
`test_series.py`.
