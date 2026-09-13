"""Isolated processes ensure CUDA allocations are released on success/failure/cancel."""

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

from filelock import FileLock, Timeout

from ..config import ROOT
from .gpu import GPUManager
from .hub import ModelHub, ModelNotReady


class LocalRunner:
    def __init__(self, settings):
        self.settings = settings
        self.hub = ModelHub(settings.cache_dir)
        self.gpu = GPUManager()

    async def run(self, role: str, payload: dict, job_id: str):
        spec = self.settings.models.models[role]
        manifest = self.hub.resolve(spec)
        self.settings.cache_dir.mkdir(parents=True, exist_ok=True)
        async with self.gpu.acquire(
            role, spec.priority, spec.timeout_seconds, {"job_id": job_id}
        ):
            # Also guard against other worker instances using this model cache.
            lock = FileLock(str(self.settings.cache_dir / "inference.lock"))
            deadline = asyncio.get_running_loop().time() + spec.timeout_seconds
            while True:
                try:
                    lock.acquire(timeout=0)
                    break
                except Timeout:
                    if asyncio.get_running_loop().time() > deadline:
                        raise TimeoutError(
                            "Timed out waiting for the local inference lock"
                        )
                    await asyncio.sleep(0.1)
            try:
                with tempfile.TemporaryDirectory(prefix="inference-") as temporary:
                    request = Path(temporary) / "request.json"
                    result = Path(temporary) / "result.json"
                    log = Path(temporary) / "runtime.log"
                    request.write_text(
                        json.dumps(
                            {
                                "spec": spec.model_dump(),
                                "snapshot": manifest["snapshot"],
                                "extras": manifest.get("extras", {}),
                                "payload": payload,
                            }
                        )
                    )
                    env = {
                        **os.environ,
                        "HF_HUB_OFFLINE": "1",
                        "TRANSFORMERS_OFFLINE": "1",
                        "HF_HUB_DISABLE_TELEMETRY": "1",
                        "TOKENIZERS_PARALLELISM": "false",
                        "ORCHESTRATOR_PARENT_PID": str(os.getpid()),
                    }
                    # Inference has no need for Hub credentials.
                    env.pop("HF_TOKEN", None)
                    with log.open("wb") as stderr:
                        spawn = asyncio.create_task(
                            asyncio.create_subprocess_exec(
                                sys.executable,
                                "-m",
                                "app.models.runtime",
                                str(request),
                                str(result),
                                cwd=ROOT,
                                env=env,
                                stdout=stderr,
                                stderr=stderr,
                            )
                        )
                        try:
                            process = await asyncio.shield(spawn)
                        except asyncio.CancelledError:
                            process = await spawn
                            if process.returncode is None:
                                process.kill()
                                await process.wait()
                            raise
                        try:
                            await asyncio.wait_for(process.wait(), spec.timeout_seconds)
                            if process.returncode:
                                # Child writes bounded errors to JSON; don't expose environment logs.
                                failure = (
                                    json.loads(result.read_text())
                                    if result.exists()
                                    else {
                                        "error": "Local runtime exited unexpectedly; check optional dependencies and model compatibility"
                                    }
                                )
                                error_type = (
                                    ModelNotReady
                                    if failure.get("kind") == "configuration"
                                    else RuntimeError
                                )
                                raise error_type(failure["error"])
                            output = json.loads(result.read_text())
                        finally:
                            if process.returncode is None:
                                process.kill()
                                await process.wait()
                    return {
                        **output,
                        "provenance": {
                            "role": role,
                            "runtime": spec.runtime,
                            "repo_id": spec.repo_id,
                            "revision": manifest["revision"],
                            "config_fingerprint": manifest["fingerprint"],
                        },
                    }
            finally:
                lock.release()
