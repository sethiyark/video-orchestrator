"""Dashboard-triggered model provisioning: weight downloads and runtime installs.

State lives in the API process only. Each operation key (``download:<role>`` or
``install:<extra>``) runs at most once at a time; a second start is rejected
with :class:`SetupBusy`. Installs are the fixed ``uv sync --extra <extra>``
command with an allowlisted extra — never arbitrary shell.
"""

from __future__ import annotations

import asyncio
import importlib
import logging
import os
import re
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from ..config import ROOT, RUNTIME_EXTRAS, ModelSpec
from .hub import ModelHub

log = logging.getLogger(__name__)

TOKEN_PATTERN = re.compile(r"hf_[A-Za-z0-9]{8,}")
LOG_LINES = 50


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _default_command(extra: str) -> list[str]:
    return ["uv", "sync", "--extra", extra]


class SetupBusy(RuntimeError):
    pass


@dataclass
class SetupTask:
    key: str
    state: str = "idle"  # idle | running | done | failed
    started_at: str | None = None
    ended_at: str | None = None
    error: str | None = None
    log: deque[str] = field(default_factory=lambda: deque(maxlen=LOG_LINES))

    def snapshot(self) -> dict:
        return {
            "state": self.state,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "error": self.error,
            "log": list(self.log),
        }


class SetupManager:
    def __init__(
        self,
        hub: ModelHub,
        root: Path = ROOT,
        command_factory: Callable[[str], list[str]] | None = None,
    ):
        self.hub = hub
        self.root = root
        self.command_factory = command_factory or _default_command
        self.tasks: dict[str, SetupTask] = {}
        self._jobs: dict[str, asyncio.Task] = {}

    # ---- status -----------------------------------------------------------

    def status(self, key: str) -> dict:
        return self.tasks.get(key, SetupTask(key)).snapshot()

    def is_running(self, key: str) -> bool:
        task = self.tasks.get(key)
        return bool(task and task.state == "running")

    def any_running(self) -> bool:
        return any(task.state == "running" for task in self.tasks.values())

    # ---- scrubbing --------------------------------------------------------

    @staticmethod
    def scrub(text: str) -> str:
        token = os.getenv("HF_TOKEN")
        if token:
            text = text.replace(token, "***")
        return TOKEN_PATTERN.sub("***", text)

    # ---- starting ---------------------------------------------------------

    def _begin(self, key: str, operation: Callable[[], Awaitable[None]]) -> dict:
        if self.is_running(key):
            raise SetupBusy(f"{key.replace(':', ' for ')} is already running")
        task = SetupTask(key, state="running", started_at=_now())
        self.tasks[key] = task
        self._jobs[key] = asyncio.get_running_loop().create_task(
            self._guard(task, operation)
        )
        return task.snapshot()

    async def _guard(
        self, task: SetupTask, operation: Callable[[], Awaitable[None]]
    ) -> None:
        try:
            await operation()
            task.state = "done"
        except asyncio.CancelledError:
            task.state = "failed"
            task.error = "Cancelled"
            raise
        except Exception as exc:  # noqa: BLE001 - hub/uv raise many types; surface them
            log.warning("model setup %s failed: %s", task.key, self.scrub(str(exc)))
            task.state = "failed"
            task.error = self.scrub(str(exc) or exc.__class__.__name__)
        finally:
            task.ended_at = _now()

    def start_download(self, role: str, spec: ModelSpec) -> dict:
        return self._begin(f"download:{role}", lambda: self._run_download(role, spec))

    def start_install(self, extra: str) -> dict:
        if extra not in RUNTIME_EXTRAS.values():
            raise ValueError(f"Unknown runtime extra: {extra}")
        return self._begin(f"install:{extra}", lambda: self._run_install(extra))

    # ---- operations -------------------------------------------------------

    async def _run_download(self, role: str, spec: ModelSpec) -> None:
        task = self.tasks[f"download:{role}"]
        task.log.append(f"Downloading {spec.repo_id}@{spec.revision}")
        manifest = await asyncio.to_thread(self.hub.download, spec)
        task.log.append(f"Downloaded {spec.repo_id}@{manifest['revision'][:12]}")

    async def _run_install(self, extra: str) -> None:
        task = self.tasks[f"install:{extra}"]
        command = self.command_factory(extra)
        env = {key: value for key, value in os.environ.items() if key != "HF_TOKEN"}
        task.log.append(self.scrub("$ " + " ".join(command)))
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=self.root,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        assert process.stdout is not None
        while line := await process.stdout.readline():
            task.log.append(self.scrub(line.decode(errors="replace").rstrip()))
        code = await process.wait()
        if code != 0:
            raise RuntimeError(f"{command[0]} exited with status {code}")
        importlib.invalidate_caches()
