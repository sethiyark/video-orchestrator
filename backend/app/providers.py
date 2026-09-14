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
    async def execute(self, stage: str, job: dict, attempt: int = 0) -> dict: ...


def mock_storyboard(title: str) -> dict:
    """A small chaptered storyboard in the real schema shape, so the dashboard
    shows chapters and image prompts without any model."""
    scenes = [
        ("ChapterTitle", {"title": title, "subtitle": "What it is and why it matters"}),
        (
            "DefinitionCard",
            {"title": title, "body": f"{title} in one sentence, for engineers."},
        ),
        (
            "AnimatedFlowDiagram",
            {"title": "How it works", "nodes": ["Question", "Explanation", "Takeaway"]},
        ),
        (
            "CodeBlock",
            {
                "title": "A minimal example",
                "language": "python",
                "code": "def explain(topic):\n    return f\"{topic} explained\"",
            },
        ),
        (
            "Outro",
            {"title": "Recap", "takeaways": ["Mock takeaway one", "Mock takeaway two"]},
        ),
    ]
    return {
        "scenes": [
            {
                "scene_id": f"scene_{index:03d}",
                "narration_text": f"Mock narration for scene {index}.",
                "duration_seconds": 8,
                "image_prompt": f"Illustration for {title}, scene {index}",
                "component": component,
                "props": props,
            }
            for index, (component, props) in enumerate(scenes, 1)
        ],
        "chapters": [
            {
                "chapter_id": "chapter_01",
                "title": f"Introducing {title}",
                "tagline": "The core idea",
                "first_scene": "scene_001",
                "last_scene": "scene_003",
                "hero_prompt": f"A wide illustration introducing {title}",
                "accent": 0,
            },
            {
                "chapter_id": "chapter_02",
                "title": "In practice",
                "tagline": "Code and takeaways",
                "first_scene": "scene_004",
                "last_scene": "scene_005",
                "hero_prompt": f"An engineer applying {title}",
                "accent": 1,
            },
        ],
    }


class MockProvider:
    def __init__(self, delay: float = 0.8):
        self.delay = delay

    async def execute(self, stage: str, job: dict, attempt: int = 0) -> dict:
        await asyncio.sleep(self.delay)
        title = job["title"]
        outputs = {
            "verification": {
                "message": "Mock verification only",
                "verified_claims": [],
            },
            "outline": {"sections": [{"title": title, "purpose": "Mock explanation"}]},
            "assets": {
                "images": [],
                "message": "Mock visual assets; no images generated",
            },
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
            "storyboard": mock_storyboard(title),
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
