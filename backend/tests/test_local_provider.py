import asyncio
import json
from copy import deepcopy

import pytest

from app.config import Settings
from app.local_provider import IntegrationUnavailable, LocalProvider, ReviewRequired
from app.schemas import Storyboard
from app.store import Store


class FakeRunner:
    """Answers batched JSON requests from a queue; non-LLM roles return raw dicts."""

    def __init__(self, outputs):
        self.outputs = iter(outputs)
        self.calls = []

    async def run(self, role, payload, job_id):
        self.calls.append((role, payload))
        provenance = {"repo_id": role, "revision": "fixture"}
        if "requests" not in payload:
            return {**next(self.outputs), "provenance": provenance}
        return {
            "results": [{"result": next(self.outputs)} for _ in payload["requests"]],
            "provenance": provenance,
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
        last = runner.calls[-1][1]["requests"][0]
        assert "verified_claims" in last["messages"][-1]["content"]
        assert last["schema_name"] == "Outline"
        assert "/no_think" not in last["messages"][0]["content"]

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
    provider.config.governor.critique_rounds = 1
    complete(job, "script", {"text": "Draft", "claim_ids": ["c1"]})
    with pytest.raises(ReviewRequired, match="revision budget"):
        asyncio.run(provider.execute("critique", job))
    # Five critics share one model load.
    assert len(runner.calls) == 1
    role, payload = runner.calls[0]
    assert role == "quality"
    assert len(payload["requests"]) == 5
    assert {request["seed"] for request in payload["requests"]} == set(range(42, 47))
    assert all(request["temperature"] == 0.3 for request in payload["requests"])


def test_critique_rewrites_with_required_changes_only(tmp_path):
    failing = {
        "score": 4,
        "issues": ["long"],
        "required_changes": ["cut intro"],
        "optional_changes": ["shorter title"],
    }
    passing = {"score": 9, "issues": [], "required_changes": [], "optional_changes": []}
    rewrite = {"text": "A revised and sufficiently long draft.", "claim_ids": ["c1"]}
    provider, runner, job = setup(
        tmp_path,
        [deepcopy(failing) for _ in range(5)]
        + [rewrite]
        + [deepcopy(passing) for _ in range(5)],
    )
    provider.config.governor.critique_rounds = 2
    complete(job, "verification", {"verified_claims": [{"id": "c1", "text": "DNS"}]})
    complete(job, "script", {"text": "Draft", "claim_ids": ["c1"]})
    result = asyncio.run(provider.execute("critique", job))
    assert result["approved_script"]["text"] == rewrite["text"]
    assert len(result["rounds"]) == 2
    assert [len(payload["requests"]) for _, payload in runner.calls] == [5, 1, 5]
    prompt = runner.calls[1][1]["requests"][0]["messages"][-1]["content"]
    assert "cut intro" in prompt
    assert (
        "shorter title" not in prompt and "long" not in prompt.split("issues")[0][-10:]
    )


def test_token_budget_fails_closed_before_model_load(tmp_path):
    provider, runner, job = setup(tmp_path, [])
    provider.config.models["quality"].context_size = 512
    provider.config.models["quality"].max_tokens = 64
    complete(
        job,
        "verification",
        {"verified_claims": [{"id": "c1", "text": "x" * 3000}]},
    )
    with pytest.raises(ReviewRequired, match="context budget"):
        asyncio.run(provider.execute("outline", job))
    assert runner.calls == []


def test_runtime_validation_error_is_retryable(tmp_path):
    class BrokenRunner(FakeRunner):
        async def run(self, role, payload, job_id):
            return {
                "results": [{"error": "ValueError: bad json", "kind": "validation"}],
                "provenance": {},
            }

    provider, _, job = setup(tmp_path, [])
    provider.runner = BrokenRunner([])
    with pytest.raises(RuntimeError, match="bad json"):
        asyncio.run(provider.execute("research", job))


def narration_job(tmp_path, alignment):
    provider, runner, job = setup(tmp_path, [alignment])
    folder = provider.artifacts.folder(job["id"])
    folder.mkdir(parents=True, exist_ok=True)
    audio = folder / "narration.wav"
    audio.write_bytes(b"RIFF")
    complete(
        job,
        "narration",
        {
            "text": "DNS maps names to addresses.",
            "audio": provider.artifacts.adopt(job["id"], audio),
        },
    )
    return provider, runner, job


def test_alignment_fails_closed_on_low_fidelity(tmp_path):
    provider, _, job = narration_job(
        tmp_path,
        {
            "segments": [{"text": "garbled", "start": 0, "end": 1}],
            "method": "asr_transcript",
            "fidelity": 0.4,
        },
    )
    with pytest.raises(ReviewRequired, match="fidelity 0.40") as info:
        asyncio.run(provider.execute("alignment", job))
    assert info.value.details == {"method": "asr_transcript", "fidelity": 0.4}


def test_alignment_passes_with_fidelity_and_sends_script(tmp_path):
    provider, runner, job = narration_job(
        tmp_path,
        {
            "segments": [{"text": "DNS maps names", "start": 0, "end": 1}],
            "method": "forced_alignment",
            "fidelity": 0.93,
        },
    )
    result = asyncio.run(provider.execute("alignment", job))
    assert result["method"] == "forced_alignment"
    assert runner.calls[0][1]["text"] == "DNS maps names to addresses."
    with pytest.raises(ReviewRequired, match="did not report"):
        provider.runner = FakeRunner(
            [{"segments": [{"text": "x", "start": 0, "end": 1}]}]
        )
        asyncio.run(provider.execute("alignment", job))


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


def test_truncated_script_fails_closed_against_outline(tmp_path):
    leak = {
        "text": "DNS maps domain names to IP addresses quickly.",
        "claim_ids": ["c1"],
    }
    provider, _, job = setup(tmp_path, [leak])
    complete(job, "verification", {"verified_claims": [{"id": "c1", "text": "DNS"}]})
    complete(
        job,
        "outline",
        {
            "sections": [
                {
                    "title": "DNS",
                    "purpose": "x",
                    "claim_ids": ["c1"],
                    "estimated_seconds": 600,
                }
            ]
        },
    )
    with pytest.raises(ReviewRequired, match="looks truncated"):
        asyncio.run(provider.execute("script", job))


def test_critics_receive_only_script_text_and_claims(tmp_path):
    passing = {"score": 9, "issues": [], "required_changes": [], "optional_changes": []}
    provider, runner, job = setup(tmp_path, [deepcopy(passing) for _ in range(5)])
    complete(
        job,
        "script",
        {
            "text": "Draft narration.",
            "claim_ids": ["c1"],
            "provenance": {"x": 1},
            "artifact": {},
        },
    )
    asyncio.run(provider.execute("critique", job))
    data = json.loads(runner.calls[0][1]["requests"][0]["messages"][1]["content"])
    assert data["script"] == {"text": "Draft narration.", "claim_ids": ["c1"]}
