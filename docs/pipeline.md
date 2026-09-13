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

Stages implemented: research, verification, outline, script, critique
(five independent critic prompts, bounded rewrites), storyboard (closed
component enum), assets (optional images), narration, alignment, similarity
(cosine vs prior completed similarity JSON), metadata. `render` and `upload`
raise `IntegrationUnavailable`.

Research uses **supplied excerpts**, not HTTP fetch. Quotes must appear in
excerpts. Script may not cite unverified claims.

## How it is called

Selected when `PIPELINE_MODE=local`. Worker calls `provider.execute` per
incomplete stage.

## Invariants

- System prompt treats excerpts as untrusted data, not instructions.
- Fabricated quotes fail closed.
- Scene JSON cannot contain arbitrary renderer code.
- New draft after model config/revision change.

## Related tests

[`test_local_provider.py`](../backend/tests/test_local_provider.py),
[`test_local_api.py`](../backend/tests/test_local_api.py).

## Known limitations

No web search. Similarity vs all prior jobs with similarity output, not
published-only. Storyboard retiming after Whisper is not applied to a
renderer yet.
