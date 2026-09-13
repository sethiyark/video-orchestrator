import asyncio
from copy import deepcopy

import pytest

from app.config import Settings
from app.local_provider import IntegrationUnavailable, LocalProvider, ReviewRequired
from app.schemas import Storyboard
from app.store import Store


class FakeRunner:
    def __init__(self, outputs):
        self.outputs = iter(outputs)
        self.calls = []

    async def run(self, role, payload, job_id):
        self.calls.append((role, payload))
        return {
            "result": next(self.outputs),
            "provenance": {"repo_id": role, "revision": "fixture"},
        }


def setup(tmp_path, outputs):
    settings = Settings()
    settings.artifact_dir = tmp_path / "artifacts"
    store = Store(str(tmp_path / "jobs.db"))
    runner = FakeRunner(outputs)
    provider = LocalProvider(settings, store, runner)
    job = store.create(
        "DNS",
        "",
        [
            {
                "id": "s1",
                "url": "https://example.com",
                "title": "Reference",
                "excerpt": "DNS maps domain names to IP addresses.",
            }
        ],
    )
    return provider, runner, job


def complete(job, name, output):
    stage = next(s for s in job["stages"] if s["name"] == name)
    stage["output"], stage["status"] = output, "completed"


def test_source_grounding_and_model_routing(tmp_path):
    claim = {
        "id": "c1",
        "text": "DNS maps names to addresses",
        "source_id": "s1",
        "quote": "DNS maps domain names to IP addresses.",
    }
    provider, runner, job = setup(
        tmp_path,
        [
            {"summary": "DNS", "claims": [claim]},
            {
                "verdicts": [
                    {
                        "claim_id": "c1",
                        "supported": True,
                        "confidence": 0.95,
                        "reason": "Direct quote",
                    }
                ]
            },
            {
                "sections": [
                    {
                        "title": "DNS",
                        "purpose": "Explain",
                        "claim_ids": ["c1"],
                        "estimated_seconds": 30,
                    }
                ]
            },
        ],
    )

    async def scenario():
        for stage in ["research", "verification", "outline"]:
            result = await provider.execute(stage, job)
            assert result["artifact"]["sha256"]
            complete(job, stage, result)
        assert [call[0] for call in runner.calls] == ["fast", "quality", "quality"]
        assert "verified_claims" in runner.calls[-1][1]["messages"][-1]["content"]

    asyncio.run(scenario())


def test_fabricated_quote_fails_closed(tmp_path):
    provider, _, job = setup(
        tmp_path,
        [
            {
                "summary": "DNS",
                "claims": [
                    {
                        "id": "c1",
                        "text": "Invented",
                        "source_id": "s1",
                        "quote": "This quotation was fabricated.",
                    }
                ],
            }
        ],
    )
    with pytest.raises(ReviewRequired, match="unsupported"):
        asyncio.run(provider.execute("research", job))


def test_script_cannot_reference_unverified_claims(tmp_path):
    provider, _, job = setup(
        tmp_path,
        [
            {
                "text": "This is a sufficiently long narration example.",
                "claim_ids": ["invented"],
            }
        ],
    )
    complete(
        job,
        "verification",
        {"verified_claims": [{"id": "c1", "text": "DNS maps names"}]},
    )
    with pytest.raises(ReviewRequired, match="outside"):
        asyncio.run(provider.execute("script", job))


def test_critics_have_bounded_independent_rounds(tmp_path):
    critic = {
        "score": 4,
        "issues": ["unclear"],
        "required_changes": ["revise"],
        "optional_changes": [],
    }
    provider, runner, job = setup(tmp_path, [deepcopy(critic) for _ in range(5)])
    provider.config.governor.max_attempts = 1
    complete(job, "script", {"text": "Draft", "claim_ids": ["c1"]})
    with pytest.raises(ReviewRequired, match="revision budget"):
        asyncio.run(provider.execute("critique", job))
    assert len(runner.calls) == 5
    assert all(role == "quality" for role, _ in runner.calls)


def test_scene_schema_rejects_arbitrary_code_and_live_render_is_explicit(tmp_path):
    with pytest.raises(ValueError):
        Storyboard.model_validate(
            {
                "scenes": [
                    {
                        "scene_id": "scene_001",
                        "component": "RunJavaScript",
                        "props": {"code": "alert(1)"},
                        "narration_text": "",
                        "duration_seconds": 8,
                    }
                ]
            }
        )
    provider, _, job = setup(tmp_path, [])
    with pytest.raises(IntegrationUnavailable, match="not connected"):
        asyncio.run(provider.execute("render", job))
