# Invariants

Cross-cutting rules. Weaken these only with an explicit product decision and
tests.

## GPU and processes

- Only one GPU-heavy workload via `GPUManager.acquire`. Unload hooks run even
  on failure.
- Do not load FAST and QUALITY GGUF plus diffusion at once.
- Embeddings stay on CPU.
- One model worker per database (advisory lock or SQLite file lock).
  `RUN_WORKER=false` for extra API processes.
- Inference children do not inherit `HF_TOKEN`.

## Publish and Governor

- Upload stage requires `approved_at`.
- `autonomous_publish` defaults to false. Agents cannot mutate Governor YAML
  at runtime.
- Local `render` / `upload` must not invent success. Mock may label outputs
  as simulated.

## Evidence and tools

- Local jobs require source excerpts. URLs are not fetched.
- Fabricated quotes and unverified-claim scripts fail closed.
- Storyboard components are a closed enum; no LLM shell/code execution.
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
`test_models.py`, `test_database.py`, `test_control_plane.py`.
