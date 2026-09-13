"""Content-addressed local artifacts. IDs never contain filesystem paths."""

import hashlib
import json
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

    def resolve(self, job_id, artifact_id):
        if Path(job_id).name != job_id or Path(artifact_id).name != artifact_id:
            raise ValueError("Invalid artifact identifier")
        root = (self.root / job_id).resolve()
        target = (root / artifact_id).resolve()
        if target.parent != root or not target.is_file():
            raise FileNotFoundError(artifact_id)
        return target
