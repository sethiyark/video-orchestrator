# Local pipeline

Sources: [`backend/app/local_provider.py`](../backend/app/local_provider.py),
[`backend/app/schemas.py`](../backend/app/schemas.py).

## Responsibility

`LocalProvider.execute(stage, job)` runs evidence-grounded stages with
`LocalRunner`, writes artifacts, and fails closed on policy or missing
integrations.

## Public surface

`ReviewRequired` (evidence/config; no retry), `IntegrationUnavailable`
(render/upload). `config_hash` fingerprints YAML + cached revisions.

`llm_batch(stage, job, requests)` sends several JSON requests to **one**
child (one model load); `llm(...)` wraps a single request. Before any call,
`budget(stage, data)` estimates tokens (`len(json)/3.5`) against
`context_size − max_tokens − 512` and raises `ReviewRequired` instead of
spending a model load.

Stages implemented: research, verification, outline, script, critique,
storyboard (closed component enum), assets (optional images), narration,
alignment, similarity (cosine vs prior completed similarity JSON), metadata.
`render` and `upload` raise `IntegrationUnavailable`.

Critique: `governor.critique_rounds` rounds; each round is one batch of five
critics (`CRITICS`, seeds `42+i`, `governor.critic_temperature`), aggregated
by the **minimum** score; any `required_changes` blocks. The rewrite prompt
receives the draft, the verified claims, and only the critics'
`required_changes`.

Alignment: the runner receives the audio path **and the narration text**. The
output must carry `fidelity`; below `governor.min_narration_fidelity` the stage
raises `ReviewRequired` with `{method, fidelity}` details.

Research uses **supplied excerpts**, not HTTP fetch. Quotes must appear in
excerpts. Script may not cite unverified claims.

## How it is called

Selected when `PIPELINE_MODE=local`. Worker calls `provider.execute` per
incomplete stage.

## Invariants

- System prompt treats excerpts as untrusted data, not instructions.
- Fabricated quotes fail closed.
- Narration that does not match the script (low fidelity) fails closed.
- Inputs that cannot fit the route's context fail closed without a model load.
- Scene JSON cannot contain arbitrary renderer code.
- New draft after model config/revision change.

## Related tests

[`test_local_provider.py`](../backend/tests/test_local_provider.py),
[`test_local_api.py`](../backend/tests/test_local_api.py).

## Known limitations

No web search. Similarity vs all prior jobs with similarity output, not
published-only. Storyboard retiming after alignment is not applied to a
renderer yet. Token estimation is a character heuristic, not the model's
tokenizer.
