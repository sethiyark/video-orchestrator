"""Object storage: local disk by default, S3/MinIO when STORAGE_BACKEND=s3."""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
from typing import Protocol


class ObjectStore(Protocol):
    async def put(
        self, key: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> dict: ...

    async def get(self, key: str) -> bytes: ...

    async def exists(self, key: str) -> bool: ...

    async def ping(self) -> str: ...


def _safe_key(key: str) -> str:
    path = Path(key)
    if path.is_absolute() or ".." in path.parts or not key.strip():
        raise ValueError("Object key must be a relative path without ..")
    return key.replace("\\", "/")


class LocalObjectStore:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        target = (self.root / _safe_key(key)).resolve()
        if not str(target).startswith(str(self.root.resolve())):
            raise ValueError("Object key escaped storage root")
        return target

    async def put(
        self, key: str, data: bytes, content_type: str = "application/octet-stream"
    ):
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        digest = hashlib.sha256(data).hexdigest()
        return {
            "key": _safe_key(key),
            "sha256": digest,
            "bytes": len(data),
            "content_type": content_type,
            "backend": "local",
        }

    async def get(self, key: str) -> bytes:
        path = self._path(key)
        if not path.is_file():
            raise FileNotFoundError(key)
        return path.read_bytes()

    async def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    async def ping(self) -> str:
        self.root.mkdir(parents=True, exist_ok=True)
        return "ok"


class S3ObjectStore:
    def __init__(
        self, endpoint: str, access_key: str, secret_key: str, bucket: str, region: str
    ):
        from minio import Minio

        host = endpoint.replace("https://", "").replace("http://", "")
        secure = endpoint.startswith("https://")
        self.bucket = bucket
        self.client = Minio(
            host,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
            region=region,
        )

    def _ensure_bucket(self):
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)

    async def put(
        self, key: str, data: bytes, content_type: str = "application/octet-stream"
    ):
        key = _safe_key(key)

        def write():
            from io import BytesIO

            self._ensure_bucket()
            self.client.put_object(
                self.bucket,
                key,
                BytesIO(data),
                length=len(data),
                content_type=content_type,
            )
            return hashlib.sha256(data).hexdigest()

        digest = await asyncio.to_thread(write)
        return {
            "key": key,
            "sha256": digest,
            "bytes": len(data),
            "content_type": content_type,
            "backend": "s3",
        }

    async def get(self, key: str) -> bytes:
        key = _safe_key(key)

        def read():
            response = self.client.get_object(self.bucket, key)
            try:
                return response.read()
            finally:
                response.close()
                response.release_conn()

        return await asyncio.to_thread(read)

    async def exists(self, key: str) -> bool:
        key = _safe_key(key)

        def check():
            from minio.error import S3Error

            try:
                self.client.stat_object(self.bucket, key)
                return True
            except S3Error as exc:
                if exc.code in {"NoSuchKey", "NoSuchObject"}:
                    return False
                raise

        return await asyncio.to_thread(check)

    async def ping(self) -> str:
        await asyncio.to_thread(self._ensure_bucket)
        return "ok"


def build_object_store(settings) -> ObjectStore:
    if settings.storage_backend == "s3":
        return S3ObjectStore(
            settings.s3_endpoint,
            settings.s3_access_key,
            settings.s3_secret_key,
            settings.s3_bucket,
            settings.s3_region,
        )
    return LocalObjectStore(settings.artifact_dir)
