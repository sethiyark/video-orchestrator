"""Provider boundary: replace mocks with local services without changing the worker."""

import asyncio
from typing import Protocol

STAGES = [
    "research",
    "verification",
    "outline",
    "script",
    "critique",
    "storyboard",
    "assets",
    "narration",
    "alignment",
    "similarity",
    "metadata",
    "render",
    "upload",
]


class Provider(Protocol):
    async def execute(self, stage: str, job: dict) -> dict: ...


class MockProvider:
    def __init__(self, delay: float = 0.8):
        self.delay = delay

    async def execute(self, stage: str, job: dict) -> dict:
        await asyncio.sleep(self.delay)
        title = job["title"]
        outputs = {
            "verification": {
                "message": "Mock verification only",
                "verified_claims": [],
            },
            "outline": {"sections": [{"title": title, "purpose": "Mock explanation"}]},
            "assets": {"images": [], "message": "Mock visual assets"},
            "similarity": {"message": "Mock similarity; no embedding computed"},
            "research": {
                "summary": f"Demo research brief for {title}.",
                "sources": [],
                "verified": False,
            },
            "script": {
                "text": f"[Mock script] What makes {title} interesting? Let's break it down. This placeholder demonstrates the production workflow; replace it with sourced narration."
            },
            "critique": {
                "notes": "Mock review only. Claims and source coverage require human review."
            },
            "storyboard": {
                "scenes": [
                    {
                        "component": "DefinitionCard",
                        "duration": 8,
                        "props": {"title": title},
                    },
                    {
                        "component": "AnimatedFlowDiagram",
                        "duration": 12,
                        "props": {"nodes": ["Question", "Explanation", "Takeaway"]},
                    },
                ]
            },
            "narration": {"message": "Mock narration complete; no audio generated."},
            "alignment": {"captions": [{"start": 0, "end": 8, "text": title}]},
            "render": {"message": "Mock render complete; no video file generated."},
            "metadata": {
                "title": title,
                "description": f"An explainer about {title}.",
                "tags": ["explainer", "technology"],
            },
            "upload": {
                "message": "Simulated upload after human approval. Nothing sent to YouTube."
            },
        }
        return {"provider": "mock", **outputs[stage]}
