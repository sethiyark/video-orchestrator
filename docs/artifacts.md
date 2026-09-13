# Artifacts

Source: [`backend/app/artifacts.py`](../backend/app/artifacts.py).

## Responsibility

Content-addressed files per job under `ARTIFACT_DIR`. IDs never contain
filesystem paths.

## Public surface

`put_json(job_id, data)` → `{id, sha256, bytes}` (`{sha256}.json`).
`adopt(job_id, source: Path)` moves a file to `{sha256}{suffix}`.
`resolve(job_id, artifact_id)` — basename-only, must stay under job folder.

Served at `GET /api/jobs/{id}/artifacts/{artifact_id}`.

## How it is called

`LocalProvider` after stage outputs (JSON, WAV, optional PNG).

## Invariants

`Path(job_id).name != job_id` or artifact id with extra path components →
`ValueError`. Resolved path parent must equal job root.

## Related tests

`test_local_pipeline_artifacts_and_explicit_render_boundary`.

## Known limitations

Not the same as `ObjectStore` (MinIO). Dashboard downloads use this local
tree. Compose S3 backend does not automatically replace artifact HTTP.
