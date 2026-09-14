# Series

Sources: [`backend/app/series/schema.py`](../backend/app/series/schema.py),
[`backend/app/series/store.py`](../backend/app/series/store.py),
[`backend/app/series/library.py`](../backend/app/series/library.py),
[`backend/app/series/api.py`](../backend/app/series/api.py),
[`backend/app/db/series.py`](../backend/app/db/series.py),
migrations `0003_series`, `0004_series_library`.

## Responsibility

A **series** is the shared project that video jobs can optionally belong to.
It holds:

- a versioned **bible**: voice/tone, visual style, glossary;
- **themes** (arcs within the series), each with a blurb and optional extra
  guidance;
- an **idea backlog** that turns into draft jobs;
- a **media library**: uploaded files plus job outputs promoted into it;
- a **source library**: reusable evidence excerpts.

Series guidance is **style data**. It is never evidence, never instructions,
and it cannot change Governor thresholds or budgets.

## Public surface

**Bible (`SeriesBible`, `extra="forbid"`, bounded lengths):**
- `voice`: `audience`, `tone`, `style_rules[]`, `avoid_phrases[]`.
- `visual`: `palette[]` (`#rrggbb`; three or more become the renderer's
  chapter accents), `preferred_components[]` (storyboard component names,
  the full closed enum), `image_style`, and the brand kit `logo_asset_id`,
  `intro_asset_id`, `outro_asset_id` (active `logo`/`image` assets) and
  `music_asset_id` (active `music`/`audio` asset). `PUT .../bible` rejects an
  id that is not an active asset of the right kind in that series (422).
- `glossary[]`: `{term, definition}`.

`ThemeGuidance` has the same shape. `merge(base, overlay)` concatenates lists
(skipping duplicates) and lets non-empty theme scalars replace the bible's.

**`SeriesStore(engine)`** (shares `Store.engine`):
- Series: `list`, `get`, `create` (slug from name unless given; duplicate slug
  → `SeriesConflict`), `update`, `delete`.
- Bible: `bible` (version 0 means an empty, never-saved bible),
  `bible_versions`, `put_bible` (append-only, bumps the version, stores sha256).
- Themes: `themes`, `theme`, `create_theme`, `update_theme`, `delete_theme`
  (clears `theme_id` on ideas).
- Ideas: `ideas`, `idea`, `create_idea`, `update_idea`, `delete_idea`,
  `link_job` (backlog → `started`, one winner), `release_job` (back to
  `backlog` when the job is deleted).
- `resolve_context(series_id, theme_id)` →
  `{series: {id, name}, theme: {id, name, blurb} | null, bible_version, guidance, hash}`.
  `hash` covers only `guidance` and `theme`, so re-saving identical content
  does not mark jobs stale. `current_hash` returns `None` once the series or
  theme is gone.

Lookups that miss raise `SeriesNotFound` (HTTP 404). Conflicts raise
`SeriesConflict` (HTTP 409).

**`SeriesLibrary(engine, objects=None)`:**
- Media metadata lives on the existing `assets` table (`series_id`, `name`,
  `status` `active|archived`, `provenance`). Bytes live in the `ObjectStore`
  under `series/{series_id}/{sha256}{suffix}`.
- `add` checks the declared type against `MEDIA_TYPES` (png, jpeg, webp, wav,
  mp3, mp4; **no SVG or HTML**) and magic bytes. It dedupes by object key and
  returns `duplicate: true` for an existing file.
- `assets(include_archived)`, `asset`, `update`, and `content` (returns bytes
  plus a content-hash filename).
- `visual_assets` returns active `logo`/`image` assets. `BRAND_KINDS` maps
  each bible brand-kit field to the asset kinds it may reference.
- `delete_series_media` removes library rows only.
- Sources: `sources`, `add_source` (validated as `Source`; duplicate id →
  conflict), `delete_source`, and `job_sources(ids)`, which copies excerpts
  into job source dicts.

HTTP routes are listed in [api.md](api.md).

## How it is called

**Job linkage.** `POST /api/jobs` with `series_id` (and optionally `theme_id`),
or `POST /api/series/{id}/ideas/{idea_id}/start`, snapshots
`resolve_context`. `Store.create(..., series_context, idea_id)` writes
`series_id`, `theme_id`, `idea_id`, `series_context` and `series_hash` into
the job's `context` JSON; `video_jobs` gets no new columns.

**Staleness.** Job payloads carry a computed `series_stale` (the live hash
differs from `series_hash`). When `series_stale` is true, `/run` returns 409.
`/restart` wipes the stages and rebinds the snapshot. The worker does not fail
in-flight jobs: stages only read the job's own snapshot, so they cannot mix
bible versions.

**Prompts.** `LocalProvider` passes a `series` data key and appends
`SERIES_RULE` (untrusted style data, never evidence) only for jobs with a
snapshot. The sections sent depend on the stage (`SERIES_SECTIONS`):

| Stage | Sections |
| --- | --- |
| outline, script (including critique revisions), critique | voice, glossary |
| storyboard | visual |
| metadata | voice |

The theme name and blurb are included for every one of these stages. The
`style` critic is also told to enforce the voice and glossary.
`visual.image_style` is appended to diffusion prompts as plain text. Research
and verification never receive series guidance. Standalone jobs get exactly
the prompts they had before series existed.

**Library sources.** `library_source_ids` on job creation or idea start are
copied into `job.sources`. The result must have unique ids and at most 10
sources, and it counts toward local mode's "needs a source" rule. Quote checks
run on the copies as before.

**Promotion.** `POST /api/jobs/{id}/artifacts/{artifact_id}/promote` copies a
`.png`/`.wav` artifact into the job's series library. The artifact must be a
narration `audio` or assets `images[].artifact` output of that job.
Provenance: `{origin: "promoted", job_id, artifact_id, stage, model}`.

**Storyboard assets.** `SeriesAsset` scenes (`props: {title, asset_id,
caption}`) may only reference active image/logo assets in the job's series:

- Storyboard prompt: series jobs receive `series_assets: [{id, name, kind}]`;
  standalone jobs are told not to use the component.
- Storyboard validation: an unknown, non-visual or foreign `asset_id` raises
  `ReviewRequired`.
- Assets stage: re-checks each reference and pins
  `series_assets: [{scene_id, asset_id, sha256, name}]`. An asset archived in
  between fails closed.

**Brand kit and music.** The assets stage also pins the bible's
`logo/intro/outro` assets as `assets.brand` and the music bed as
`assets.music` (the job's `render.music_asset_id` wins over the bible's
`music_asset_id`); the [renderer](rendering.md) re-hashes them before staging
and shows the logo watermark, intro/outro plates and a ducked music bed.
Standalone jobs have no brand kit and cannot set a music asset (422).

## Invariants

- Series guidance and glossary text are never evidence. Claims still need
  exact quotes from the job's own excerpts.
- A job's series snapshot is immutable until Restart. Library source edits
  never change an existing job's `sources`.
- Deleting a series or theme that any job references → 409. Deleting a job
  sets its idea back to `backlog`.
- An idea with a linked video cannot change status (409). Only backlog ideas
  can be started.
- Uploads: allowlisted types whose bytes match; size ≤
  `SERIES_ASSET_MAX_BYTES` (413); served as attachments with `nosniff` and a
  hash filename.
- `SeriesAsset` ids are validated against the library and pinned by sha256.
  No path or URL is accepted.

## Related tests

[`test_series.py`](../backend/tests/test_series.py):
- `test_migration_creates_series_tables`
- `test_series_crud_and_append_only_bible`
- `test_theme_must_belong_to_series_and_merges_guidance`
- `test_bible_change_marks_job_stale_until_restart`
- `test_idea_start_links_job_and_delete_releases_it`
- `test_local_prompts_receive_stage_specific_series_guidance`
- `test_standalone_local_prompts_are_unchanged`
- `test_glossary_cannot_stand_in_for_evidence`
- `test_asset_upload_allowlist_dedupe_and_archive`
- `test_library_sources_are_copied_into_jobs`
- `test_library_source_counts_for_local_mode_and_quotes_still_checked`
- `test_promote_media_artifact_into_series_library`
- `test_series_asset_scene_is_validated_and_pinned`
- `test_standalone_storyboard_forbids_series_assets`
- `test_brand_kit_and_music_are_validated_and_pinned`

The [renderer](rendering.md) verifies pinned `SeriesAsset` hashes before staging media.

## Known limitations

- Job↔series filtering scans job `context` JSON in Python; there is no index.
- No semantic search over ideas, glossary or sources.
- Assets are archived, never hard-deleted. Deleting a series drops its library
  rows but leaves the bytes in the object store.
- Uploads are a raw request body (not multipart) and are buffered in memory up
  to the size cap.
- `MockProvider` ignores series guidance, and its storyboard never uses
  `SeriesAsset` (it does carry chapters and image prompts).
