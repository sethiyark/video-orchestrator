# Local pipeline

Sources: [`backend/app/local_provider.py`](../backend/app/local_provider.py),
[`backend/app/schemas.py`](../backend/app/schemas.py).
Series guidance and series assets: [series.md](series.md).

## Responsibility

`LocalProvider.execute(stage, job)` runs evidence-grounded stages with
`LocalRunner`, writes artifacts, and fails closed on policy or missing
integrations.

## Public surface

`ReviewRequired(message, details, rewind_to=None)` (evidence/config; no
worker retry). With `rewind_to` naming an earlier stage, the worker may send
the job back to that stage with `details` as corrections instead of stopping
(see [providers.md](providers.md), Governor `max_rewinds`). Today only critique
sets it (`rewind_to="script"`). `IntegrationUnavailable` (render/upload). `config_hash` fingerprints YAML + cached revisions; `stage_hashes` fingerprints,
per stage, the route, that role's spec, its cached revision (and
`images_enabled` for assets). A changed config never blocks a job: the worker
records it on the job and continues (see [providers.md](providers.md)); every
stage output still carries the provenance it actually ran with.
`POST /api/jobs/{id}/restart` wipes stage outputs, stamps the live hashes, and
queues from research when the operator wants a clean run instead.

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
by the **minimum** score; any `required_changes` blocks. Critics are told the
draft is spoken voiceover with no headings or visuals to add, and that
`required_changes` is only for blocking defects a narration rewrite can
satisfy (empty when acceptable). When the rounds are exhausted the stage
writes `{rounds, last_draft}` as a review artifact and raises
`ReviewRequired(..., {review_artifact, required_changes, score},
rewind_to="script")`, where `required_changes` is the last round's per-critic
list (non-empty critics only). Critics and the
rewrite see only the draft's `text` and `claim_ids` (`script_body`), never its
provenance/artifact fields. The rewrite (`LocalProvider.rewrite`) goes
through `write_sections` over the draft's stored `sections` (a draft without
`sections` is one part measured against the whole outline): each request
carries that section's draft, all critics' `required_changes`, and the
section's verified claims, and asks for a revised `ScriptSection`.

Script: the stage requires a completed outline (`ReviewRequired` otherwise)
and writes narration one `ScriptSection` request per outline section in one
model load (`write_sections`). When the worker has rewound critique to script,
`job["corrections"]["script"]` holds the critique error's details; each
section request then also carries `required_changes` and `previous_attempt`
(that section's text from the review artifact's `last_draft`, via
`previous_draft`; `null` if the section counts differ) plus an instruction to
write a fresh version rather than lightly edit. Without corrections the
prompt is unchanged. Each request receives the brief, its
`section_number`/`section_count`, the section (`title`, `purpose`,
`estimated_seconds`, `target_words = estimated_seconds × WORDS_PER_SECOND`),
the outline's titles/purposes, and only the verified claims the section
cites (`claims_for`; all claims if it cites none). Sections are generated
independently, so a long script never depends on one `max_tokens` budget. A
section with fewer than `target_words × MIN_SCRIPT_COVERAGE (0.25)` words is
re-asked in `SCRIPT_RETRY_ROUNDS` (1) further batches that contain only the
short sections plus `previous_attempt_words` and a note with the target;
one still short afterwards raises `ReviewRequired` naming the section.
`assemble_script` joins sections with blank lines, unions `claim_ids` in
order, validates the whole as `Script`, and keeps `sections`
(`title`/`text`/`claim_ids`) in the output next to `text`/`claim_ids`.
`check_script_length` (whole script vs `outline seconds × 2.5 × 0.25`) still
runs on the script stage and every rewrite.

Storyboard: the script is split into sentences (`SENTENCE_SPLIT`, the
narration runtime's boundaries) and planned in chunks of
`STORYBOARD_CHUNK_SENTENCES` (16), one `StoryboardChunk` request per chunk in
one model load. The model receives `{"sentences": [{"n", "text"}]}` and
returns scenes as `first_sentence`/`last_sentence` + `component` + `props`;
it never re-emits narration, so output size does not grow with the script.
The chunk schema requires 1–6 sentences per scene (`MAX_SCENE_SENTENCES`).
Gaps and overlaps between scenes are not schema errors: `cover_sentences`
sorts the scenes and snaps them onto the chunk (each scene starts right after
the previous one ends, the first at the chunk's first sentence, the last ends
at its last; a scene left with no sentences is dropped; every snap is logged
at warning). Only a plan lying entirely outside its chunk raises
`ReviewRequired`. The provider then copies the exact `narration_text`, numbers `scene_NNN` ids,
sets `duration_seconds = max(words / 2.5, 2)`, and validates the assembled
`Storyboard` (a violation such as >120 scenes or a >60 s scene is
`ReviewRequired`).

Alignment: the runner receives the audio path **and the narration text**. The
output must carry `fidelity`; below `governor.min_narration_fidelity` the stage
raises `ReviewRequired` with `{method, fidelity}` details.

Series jobs: outline, script, critique, storyboard, and metadata prompts
receive the stage's slice of the job's `series_context` as a `series` data
key plus a rule that it is untrusted style data, never evidence. Standalone
jobs keep their prompts unchanged. Storyboard receives the series' active
image/logo assets and may only reference those ids in `SeriesAsset` scenes;
`visual.image_style` is appended to diffusion prompts.

Research uses **supplied excerpts**, not HTTP fetch. `LocalProvider.research`
sends one `Research` request per source in one model load (`{brief, source}`,
never the whole source list). Every quote must be found in its source's
excerpt by `locate_quote`, which compares words only: NFKC-normalised
letters and digits, case folded, with whitespace and dash-like characters
(`QUOTE_BREAKS`) collapsed to one space and all other punctuation ignored;
the claim stores the excerpt's exact spelling, never the model's. A source with an unlocatable quote is re-asked in
`RESEARCH_RETRY_ROUNDS` (1) further batches carrying `unsupported_quotes` and
a note; one still unlocatable raises `ReviewRequired` naming the source and
quote, with `{unsupported: {source_id: [quotes]}}` details. The provider
assigns claim ids `c1..cN` across sources and sets each claim's `source_id`
from the request, so duplicate or wrong ids from the model cannot leak. Zero
claims overall is `ReviewRequired`. Per-source summaries are joined with blank
lines. Script may not cite unverified claims.

## How it is called

Selected when `PIPELINE_MODE=local`. Worker calls `provider.execute` per
incomplete stage.

## Invariants

- System prompt treats excerpts as untrusted data, not instructions.
- Fabricated quotes fail closed.
- Narration that does not match the script (low fidelity) fails closed.
- Inputs that cannot fit the route's context fail closed without a model load.
- Scene JSON cannot contain arbitrary renderer code.
- Storyboard narration is copied from the script, never model-written.
- Model output length is bounded by the grammar where llama.cpp allows it;
  leaked reasoning is rejected before it becomes stage output.
- Series guidance never reaches research/verification and cannot satisfy a
  claim; `SeriesAsset` ids outside the job's active series images/logos fail
  closed, at storyboard and again when pinned.
- A model config/revision change is recorded per job (`config_changes`) and
  per stage output (provenance); it does not stop a job.

## Related tests

[`test_local_provider.py`](../backend/tests/test_local_provider.py),
[`test_local_api.py`](../backend/tests/test_local_api.py),
[`test_series.py`](../backend/tests/test_series.py).

## Known limitations

No web search. Similarity vs all prior jobs with similarity output, not
published-only. No renderer consumes `SeriesAsset` scenes. Storyboard retiming after alignment is not applied to a
renderer yet. Token estimation is a character heuristic, not the model's
tokenizer.
