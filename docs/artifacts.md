# Artifacts

Source: [`backend/app/artifacts.py`](../backend/app/artifacts.py).

## Responsibility

Content-addressed files per job under `ARTIFACT_DIR`. IDs never contain
filesystem paths.

## Public surface

`put_json(job_id, data)` → `{id, sha256, bytes}` (`{sha256}.json`).
`adopt(job_id, source: Path)` moves a file to `{sha256}{suffix}`;
`adopt_copy` copies instead (cache hits keep the cached file).
`resolve(job_id, artifact_id)` — basename-only, must stay under job folder.

Shared image cache under `ARTIFACT_DIR/cache/images/`: `cache_key(*parts)`
hashes the JSON of its parts (the assets stage passes the styled prompt, the
model spec and revision, the seed and the size — never a URL or path);
`cached_image(key)` finds `{key}.*`; `store_cached(key, source)` copies a
generated file in. Keys are basename-checked like artifact ids.

Served at `GET /api/jobs/{id}/artifacts/{artifact_id}`.

## How it is called

`LocalProvider` after stage outputs (JSON, WAV, generated/cached/uploaded
images, rendered MP4); the image relay endpoint adopts uploads directly.

## Invariants

`Path(job_id).name != job_id` or artifact id with extra path components →
`ValueError`. Resolved path parent must equal job root.

## Related tests

`test_local_pipeline_artifacts_and_explicit_render_boundary`,
`test_images_are_batched_hero_first_and_cached_across_jobs`.

## Known limitations

Not the same as `ObjectStore` (MinIO). Dashboard downloads use this local
tree. Compose S3 backend does not automatically replace artifact HTTP.
