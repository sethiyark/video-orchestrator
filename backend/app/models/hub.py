import hashlib
import json
import os
from pathlib import Path

from filelock import FileLock
from huggingface_hub import HfApi, snapshot_download

from ..config import ModelSpec


class ModelNotReady(RuntimeError):
    pass


def fingerprint(spec: ModelSpec):
    return hashlib.sha256(spec.model_dump_json().encode()).hexdigest()


class ModelHub:
    def __init__(self, cache_dir: Path):
        self.root = cache_dir

    def manifest_path(self, spec):
        return self.root / "manifests" / f"{fingerprint(spec)}.json"

    def download(self, spec: ModelSpec):
        """Explicit provisioning only; pin moving refs before downloading."""
        path = self.manifest_path(spec)
        path.parent.mkdir(parents=True, exist_ok=True)
        with FileLock(str(path) + ".lock"):
            token = os.getenv("HF_TOKEN") or False
            commit = (
                HfApi(token=token).model_info(spec.repo_id, revision=spec.revision).sha
            )
            snapshot = Path(
                snapshot_download(
                    repo_id=spec.repo_id,
                    revision=commit,
                    allow_patterns=spec.files,
                    cache_dir=self.root / "hub",
                    token=token,
                )
            )
            files = sorted(
                str(file.relative_to(snapshot))
                for file in snapshot.rglob("*")
                if file.is_file()
            )
            if not files or (spec.filename and spec.filename not in files):
                raise ModelNotReady(
                    "Download did not contain the configured model file; check files and filename"
                )
            manifest = {
                "repo_id": spec.repo_id,
                "revision": commit,
                "snapshot": str(snapshot.resolve()),
                "files": files,
                "fingerprint": fingerprint(spec),
            }
            temporary = path.with_suffix(".tmp")
            temporary.write_text(json.dumps(manifest, indent=2))
            temporary.replace(path)
            return manifest

    def resolve(self, spec: ModelSpec):
        path = self.manifest_path(spec)
        if not path.exists():
            raise ModelNotReady(
                f"Model {spec.repo_id} is not prepared. Run python -m app.models.cli download ROLE"
            )
        manifest = json.loads(path.read_text())
        snapshot = Path(manifest["snapshot"])
        if not snapshot.is_dir() or not all(
            (snapshot / file).is_file() for file in manifest["files"]
        ):
            raise ModelNotReady(
                "Model cache is incomplete; run the download command again"
            )
        return manifest
