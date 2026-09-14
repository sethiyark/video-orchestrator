"""Temporal worker. Requires TEMPORAL_TARGET. Does not generate video content."""

import asyncio
import os

from temporalio.client import Client
from temporalio.worker import Worker

from .workflows import HealthWorkflow

TASK_QUEUE = "video-orchestrator"


async def serve(target: str):
    client = await Client.connect(target)
    worker = Worker(client, task_queue=TASK_QUEUE, workflows=[HealthWorkflow])
    await worker.run()


def main():
    target = os.getenv("TEMPORAL_TARGET")
    if not target:
        raise SystemExit("TEMPORAL_TARGET is required to start the Temporal worker")
    asyncio.run(serve(target))


if __name__ == "__main__":
    main()
