# Domain

Sources: [`backend/app/domain/states.py`](../backend/app/domain/states.py),
[`backend/app/domain/scoring.py`](../backend/app/domain/scoring.py).

## Responsibility

v2 `VideoState` machine (fail closed) and deterministic topic scoring.
Component scores are supplied by providers, not an LLM vote.

## Public surface

`VideoState` enum, `TRANSITIONS`, `can_transition`, `transition` →
`IllegalStateTransition`.

`TopicComponents` / `TopicOpportunity`, `normalize_weights`,
`opportunity_score`, `scored_opportunity`. Competition is inverted
(`1 - competition`). Weights must match `REQUIRED_COMPONENTS` exactly.

Weights in Governor YAML `opportunity_weights`.

## How it is called

Unit tests and future Temporal/discovery code. The v1 worker does **not**
persist `VideoState` on `video_jobs.status`.

## Invariants

Illegal transitions raise; they are not coerced. Weights ≥ 0 and sum > 0.

## Related tests

`test_illegal_state_transitions_are_rejected`,
`test_opportunity_score_is_deterministic_and_penalizes_competition`.

## Known limitations

Discovery providers that fill `TopicComponents` are not wired. No
`app/domain/critics.py` yet.
