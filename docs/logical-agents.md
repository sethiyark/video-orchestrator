# Logical agents

Sources: [`backend/app/local_provider.py`](../backend/app/local_provider.py),
[`backend/app/governor/`](../backend/app/governor/), [`backend/app/schemas.py`](../backend/app/schemas.py).

## Responsibility

Agents are **logical**: typed stage functions with an implicit tool allowlist.
They do not own the GPU, retries, or publish rights. The Channel Governor can
always refuse. They share one or two model processes and run sequentially.

The in-process pipeline implements a **subset** of the catalog below as stages
on `LocalProvider.execute`. The rest is target design (see
[`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md)); do not treat unbuilt
agents as live code.

## What exists today

| Stage / role | Implemented as | LLM? |
| --- | --- | --- |
| Channel Governor | YAML + [`ChannelGovernor`](../backend/app/governor/schema.py) | no |
| Orchestrator | FastAPI in-process worker; Temporal `HealthWorkflow` only | no |
| Research / verification / outline / script / critics / storyboard | `LocalProvider` + FAST/QUALITY routes | yes |
| Assets | programmatic skip unless `images_enabled` | optional |
| Voice / alignment | Kokoro / Whisper via `LocalRunner` | no generative LLM |
| Similarity | CPU embeddings vs prior jobs | no generative LLM |
| Metadata | FAST/QUALITY JSON | yes |
| Render / upload | explicit `IntegrationUnavailable` in local mode; mock simulated messages | no |

`AgentContext` / Temporal activities / versioned `backend/prompts/` files are
**not** in the tree yet. Critic aggregation lives in `local_provider`, not
`app/domain/critics.py`.

## Target catalog (not all built)

Prefer domain models (`Research`, `Verification`, `Outline`, …) over `data: dict`.

| Agent | LLM? | Tools | Output |
| --- | --- | --- | --- |
| Channel Governor | no | none | admit / reject / require human |
| Orchestrator | no | Temporal, store, alerts | workflow handles |
| Opportunity discovery | scoring code; optional FAST extract | trends, youtube_search, rss, reddit, analytics, comments (providers optional) | `TopicOpportunity` |
| Research | FAST then QUALITY | web_search, fetch_url, retrieve_memory | sources + unverified claims |
| Fact verifier | QUALITY | retrieve_sources (no web unless configured) | verified / rejected claims |
| Content angle | QUALITY | retrieve_verified_claims, retrieve_memory | angle JSON |
| Outline | QUALITY | claims, angle, memory | sections |
| Script writer | QUALITY | verified claims, outline, angle, memory | narration script |
| Critics (5) | QUALITY, separate prompts | script, claims, memory, similarity scores | structured scores |
| Similarity engine | embeddings, no generative LLM | embed, retrieve corpus | similarity JSON |
| Storyboard | QUALITY | script, scene schemas | scene list (closed component enum) |
| Asset manager | optional image model | object store, GPU queue, hash/dedupe | asset records |
| Voice | Kokoro | TTS provider | WAV + hash + settings |
| Alignment | Whisper | audio file | segment/word timings |
| Render | no LLM | Remotion + FFmpeg | MP4 |
| Video QC | deterministic first; optional QUALITY | ffprobe, manifests | `QcResult` |
| Packaging | FAST/QUALITY | memory, similarity | titles, descriptions, chapters |
| Thumbnail | programmatic compose; optional image | renderer | PNG + concept JSON |
| Compliance | rules + optional QUALITY | governor, claims, metadata | pass / warn / human / reject |
| YouTube publisher | no | youtube_* | private video id |
| Analytics ingest | no | youtube analytics | snapshots |
| Postmortem | QUALITY after min-n | snapshots, memory | lessons |
| Comments | FAST extract | youtube comments | topics/FAQ/suggestions; **no auto-reply** by default |

## Tool allowlists (non-negotiable)

Writer cannot search the web or upload. Publisher cannot call the LLM. Research
cannot write YouTube metadata. Compliance cannot override Governor.

## Critic loop (local pipeline)

```text
draft → five critics in one model load (seeds 42+i, critic_temperature)
  → aggregate (MINIMUM score; any required_changes fail)
  → pass Governor min_script_score
  → else required_changes only → rewrite (script route)
  → critique_rounds exhausted → ReviewRequired
```

Writer does not score itself. The strictest critic decides; the mean is not
used.

## Prompts

Target: versioned files under `backend/prompts/<agent>/vN.md`. Today,
instructions are inline in `LocalProvider`. No secrets in logs.

## What we will not build

Engagement bots, fake views, auto-likes, auto-subscribe, mass comments,
deceptive packaging, copyright circumvention, unbounded scrapers, shell/code
execution from LLM output, recursive agent spawning, many concurrent GPU
models, full text-to-video as a dependency.

## Related tests

`test_source_grounding_and_model_routing`, `test_critics_have_bounded_independent_rounds`,
`test_critique_rewrites_with_required_changes_only`
in [`backend/tests/test_local_provider.py`](../backend/tests/test_local_provider.py).
