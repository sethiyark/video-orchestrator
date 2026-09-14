from temporalio import workflow


@workflow.defn
class HealthWorkflow:
    @workflow.run
    async def run(self, ping: str = "ok") -> str:
        return ping
