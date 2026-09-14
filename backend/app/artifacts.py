"""Content-addressed local artifacts. IDs never contain filesystem paths."""

import hashlib
import json
import shutil
from pathlib import Path


class Artifacts:
    def __init__(self, root: Path):
        self.root = root

    def folder(self, job_id):
        path = self.root / job_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def put_json(self, job_id, data):
        content = json.dumps(data, sort_keys=True, indent=2).encode()
        digest = hashlib.sha256(content).hexdigest()
        target = self.folder(job_id) / f"{digest}.json"
        target.write_bytes(content)
        return {"id": target.name, "sha256": digest, "bytes": len(content)}

    def adopt(self, job_id, source: Path):
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        target = self.folder(job_id) / f"{digest}{source.suffix}"
        source.replace(target)
        return {"id": target.name, "sha256": digest, "bytes": target.stat().st_size}

    def cache_key(self, *parts) -> str:
        """Content key for a generated image: the exact prompt, the model
        fingerprint and the sampling parameters. Never a URL or a path."""
        return hashlib.sha256(json.dumps(parts, sort_keys=True).encode()).hexdigest()

    def cached_image(self, key: str) -> Path | None:
        """A previously generated image for ``key``, shared across jobs."""
        if Path(key).name != key:
            raise ValueError("Invalid cache key")
        for candidate in (self.root / "cache/images").glob(f"{key}.*"):
            if candidate.is_file():
                return candidate
        return None

    def store_cached(self, key: str, source: Path) -> Path:
        """Copy ``source`` into the shared image cache under ``key``."""
        if Path(key).name != key:
            raise ValueError("Invalid cache key")
        folder = self.root / "cache/images"
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / f"{key}{source.suffix}"
        shutil.copyfile(source, target)
        return target

    def adopt_copy(self, job_id, source: Path):
        """Like ``adopt`` but leaves ``source`` in place (cache hits)."""
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        target = self.folder(job_id) / f"{digest}{source.suffix}"
        if not target.exists():
            shutil.copyfile(source, target)
        return {"id": target.name, "sha256": digest, "bytes": target.stat().st_size}

    def resolve(self, job_id, artifact_id):
        if Path(job_id).name != job_id or Path(artifact_id).name != artifact_id:
            raise ValueError("Invalid artifact identifier")
        root = (self.root / job_id).resolve()
        target = (root / artifact_id).resolve()
        if target.parent != root or not target.is_file():
            raise FileNotFoundError(artifact_id)
        return target
