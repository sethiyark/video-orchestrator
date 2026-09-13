from temporalio.client import Client

TASK_QUEUE = "video-orchestrator"


async def check_temporal(target: str | None) -> str:
    if not target:
        return "disabled"
    import asyncio

    await asyncio.wait_for(Client.connect(target), timeout=2)
    return "ok"
