# Object storage

Source: [`backend/app/storage/objects.py`](../backend/app/storage/objects.py).

## Responsibility

`ObjectStore` protocol: `put`, `get`, `exists`, `ping`. Local disk by default;
MinIO/S3 when `STORAGE_BACKEND=s3`.

## Public surface

`LocalObjectStore(root)` writes under `artifact_dir` with SHA-256 metadata.
`S3ObjectStore` uses Minio client, creates bucket if missing.
`build_object_store(settings)` selects backend.

Keys must be relative, no `..`, no empty, no absolute paths. Escape of
storage root is rejected.

## How it is called

`create_app` for health `storage` probe. Pipeline stages still primarily use
`Artifacts` for job media.

## Invariants

Health: storage is a **required** dependency (`ok` required, unlike redis/
temporal which may be `disabled`).

## Related tests

`test_local_object_store_hashes_and_rejects_escape`.

## Known limitations

No multipart, no presigned UI URLs. Default uvicorn does not set S3.
