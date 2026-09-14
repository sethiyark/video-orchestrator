"""Priority queue for exclusive local inference; lower priority number runs first."""

import asyncio
import heapq
import itertools
from contextlib import asynccontextmanager


class GPUManager:
    def __init__(self):
        self.condition = asyncio.Condition()
        self.queue = []
        self.counter = itertools.count()
        self.active = None

    @asynccontextmanager
    async def acquire(
        self, resource, priority=10, timeout=600, metadata=None, unload=None
    ):
        entry = (priority, next(self.counter), resource, metadata or {})
        async with self.condition:
            heapq.heappush(self.queue, entry)
            try:
                await asyncio.wait_for(
                    self.condition.wait_for(
                        lambda: self.active is None and self.queue[0] == entry
                    ),
                    timeout,
                )
                heapq.heappop(self.queue)
                self.active = entry
            except BaseException:
                self.queue.remove(entry)
                heapq.heapify(self.queue)
                self.condition.notify_all()
                raise
        try:
            yield
        finally:
            try:
                if unload:
                    await unload()
            finally:
                async with self.condition:
                    self.active = None
                    self.condition.notify_all()

    def status(self):
        def describe(entry):
            return {"priority": entry[0], "resource": entry[2], "metadata": entry[3]}

        return {
            "active": describe(self.active) if self.active else None,
            "queued": [describe(item) for item in sorted(self.queue)],
        }
