# Channel Governor

Sources: [`backend/app/governor/schema.py`](../backend/app/governor/schema.py),
[`backend/config/default.yaml`](../backend/config/default.yaml).

## Responsibility

Deterministic channel policy. Logical agents **cannot mutate** this object.
Loaded from YAML at process start.

## Public surface

`ChannelGovernor`: channel caps, content thresholds, `automation.autonomous_publish`
(default false), `comments.automatic_reply` (default false), `external_llm.enabled`
(default false), budgets, `human_required` gates, observability, opportunity
weights.

Helpers: `may_publish_without_human`, `may_auto_reply`, `may_use_external_llm`,
`allow_long_form` / `allow_short`, `allow_attempt`, `script_passes`,
`research_passes`, `similarity_passes`, `debit_allowed`, `requires_human`.

## How it is called

`Settings.channel_governor`. Exposed (redacted) on `GET /api/system`. Local
pipeline uses content thresholds and attempt budgets;
`budgets.max_image_generations_per_video` (default 120, max 120) caps the
assets stage together with the model profile's `max_images`.

## Invariants

`extra="forbid"` on nested models. `autonomous_publish` stays false unless the
operator changes YAML and the user explicitly asked for that behaviour in
code.

## Related tests

`test_governor_enforces_caps_and_human_gates` in `test_control_plane.py`.

## Known limitations

Not yet applied to a Temporal video workflow or YouTube publisher. Health
endpoint reports `approval_required` from `may_publish_without_human()`.
