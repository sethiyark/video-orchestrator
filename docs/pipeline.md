# Local pipeline

Sources: [`backend/app/local_provider.py`](../backend/app/local_provider.py),
[`backend/app/schemas.py`](../backend/app/schemas.py).
Series guidance and series assets: [series.md](series.md).

## Responsibility

`LocalProvider.execute(stage, job)` runs evidence-grounded stages with
`LocalRunner`, writes artifacts, and fails closed on policy or missing
integrations.

## Public surface

`ReviewRequired` (evidence/config; no retry), `IntegrationUnavailable`
(render/upload). `config_hash` fingerprints YAML + cached revisions.
`POST /api/jobs/{id}/restart` wipes stage outputs, stamps the live hash, and
queues from research so a config change cannot mix with prior artifacts.

`llm_batch(stage, job, requests)` sends several JSON requests to **one**
child (one model load); `llm(...)` wraps a single request. Before any call,
`budget(stage, data)` estimates tokens (`len(json)/3.5`) against
`context_size − max_tokens − 512` and raises `ReviewRequired` instead of
spending a model load.

Stages implemented: research, verification, outline, script, critique,
storyboard (closed component enum: `DefinitionCard`, `AnimatedFlowDiagram`,
`BulletReveal`, `ImagePan`, `SeriesAsset`), assets (optional images; pins
`SeriesAsset` references by sha256), narration,
alignment, similarity (cosine vs prior completed similarity JSON), metadata.
`render` and `upload` raise `IntegrationUnavailable`.

Critique: `governor.critique_rounds` rounds; each round is one batch of five
critics (`CRITICS`, seeds `42+i`, `governor.critic_temperature`), aggregated
by the **minimum** score; any `required_changes` blocks. Critics and the
rewrite see only the draft's `text` and `claim_ids` (`script_body`), never its
provenance/artifact fields. The rewrite prompt receives the draft, the
verified claims, and only the critics' `required_changes`.

Script length: `check_script_length` runs on the script stage and on every
critique rewrite. A script with fewer than
`outline seconds × WORDS_PER_SECOND (2.5) × MIN_SCRIPT_COVERAGE (0.25)` words
raises `ReviewRequired` as truncated or off-task, so a broken draft never
reaches the critics. Skipped when there is no outline.

Series jobs: outline, script, critique, storyboard, and metadata prompts
receive the stage's slice of the job's `series_context` as a `series` data
key plus a rule that it is untrusted style data, never evidence. Standalone
jobs keep their prompts unchanged. Storyboard receives the series' active
image/logo assets and may only reference those ids in `SeriesAsset` scenes;
`visual.image_style` is appended to diffusion prompts.

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
- Model output length is bounded by the grammar where llama.cpp allows it;
  leaked reasoning is rejected before it becomes stage output.
- Series guidance never reaches research/verification and cannot satisfy a
  claim; `SeriesAsset` ids outside the job's active series images/logos fail
  closed, at storyboard and again when pinned.
- New draft after model config/revision change.

## Related tests

[`test_local_provider.py`](../backend/tests/test_local_provider.py),
[`test_local_api.py`](../backend/tests/test_local_api.py),
[`test_series.py`](../backend/tests/test_series.py).

## Known limitations

No web search. Similarity vs all prior jobs with similarity output, not
published-only. No renderer consumes `SeriesAsset` scenes. Storyboard retiming after alignment is not applied to a
renderer yet. Token estimation is a character heuristic, not the model's
tokenizer.
