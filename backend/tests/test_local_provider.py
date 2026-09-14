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
    provider, runner, job = setup(
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
        ]
        * 2,
    )
    with pytest.raises(ReviewRequired, match="unsupported") as info:
        asyncio.run(provider.execute("research", job))
    # One re-ask naming the bad quote, then fail closed with details.
    assert [len(payload["requests"]) for _, payload in runner.calls] == [1, 1]
    retry = json.loads(runner.calls[1][1]["requests"][0]["messages"][1]["content"])
    assert retry["unsupported_quotes"] == ["This quotation was fabricated."]
    assert info.value.details["unsupported"] == {
        "s1": ["This quotation was fabricated."]
    }


def test_research_quotes_tolerate_flattened_punctuation():
    from app.local_provider import locate_quote

    excerpt = "The study \u201cGrind size\u201d found\u00a0that finer\u2014not coarser\u2014grinds extract more."
    assert (
        locate_quote(
            'the study "grind size" found that finer - not coarser - grinds', excerpt
        )
        == "The study \u201cGrind size\u201d found\u00a0that finer\u2014not coarser\u2014grinds"
    )
    assert locate_quote("finer grinds extract less", excerpt) is None
    assert locate_quote("   ", excerpt) is None


def test_research_runs_one_request_per_source_and_owns_ids(tmp_path):
    provider, runner, job = setup(
        tmp_path,
        [
            {
                "summary": "First",
                "claims": [
                    {
                        "id": "c1",
                        "text": "Maps names",
                        "source_id": "wrong",
                        "quote": "dns maps domain names",
                    }
                ],
            },
            {
                "summary": "Second",
                "claims": [
                    {
                        "id": "c1",
                        "text": "Caches",
                        "source_id": "s2",
                        "quote": "Resolvers cache answers",
                    },
                    {
                        "id": "c2",
                        "text": "Short TTL",
                        "source_id": "s2",
                        "quote": "for the TTL",
                    },
                ],
            },
        ],
    )
    job["sources"].append(
        {
            "id": "s2",
            "url": "https://example.com/ttl",
            "title": "TTL",
            "excerpt": "Resolvers cache answers for the TTL.",
        }
    )
    result = asyncio.run(provider.execute("research", job))
    assert len(runner.calls) == 1
    requests = runner.calls[0][1]["requests"]
    assert [
        json.loads(r["messages"][1]["content"])["source"]["id"] for r in requests
    ] == [
        "s1",
        "s2",
    ]
    assert all(
        "sources" not in json.loads(r["messages"][1]["content"]) for r in requests
    )
    assert [(c["id"], c["source_id"]) for c in result["claims"]] == [
        ("c1", "s1"),
        ("c2", "s2"),
        ("c3", "s2"),
    ]
    # Quotes are stored exactly as the excerpt spells them.
    assert result["claims"][0]["quote"] == "DNS maps domain names"
    assert result["summary"] == "First\n\nSecond"
    assert result["verified"] is False


def test_research_retry_recovers_a_source(tmp_path):
    good = {
        "id": "c1",
        "text": "Maps",
        "source_id": "s1",
        "quote": "DNS maps domain names to IP addresses.",
    }
    provider, runner, job = setup(
        tmp_path,
        [
            {"summary": "x", "claims": [{**good, "quote": "Made up quote here."}]},
            {"summary": "x", "claims": [good]},
        ],
    )
    result = asyncio.run(provider.execute("research", job))
    assert [len(payload["requests"]) for _, payload in runner.calls] == [1, 1]
    assert result["claims"][0]["quote"] == good["quote"]


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
    complete(job, "outline", {"sections": [section("DNS", 10)]})
    with pytest.raises(ReviewRequired, match="outside"):
        asyncio.run(provider.execute("script", job))


def section(title, seconds, claim_ids=("c1",)):
    return {
        "title": title,
        "purpose": f"Explain {title}",
        "claim_ids": list(claim_ids),
        "estimated_seconds": seconds,
    }


def words(n, seed="word"):
    return " ".join(f"{seed}{i}" for i in range(n)) + "."


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


def card(first, last):
    return {
        "first_sentence": first,
        "last_sentence": last,
        "component": "DefinitionCard",
        "props": {"title": "DNS", "body": "Names to addresses"},
    }


def test_storyboard_plans_sentence_chunks_and_copies_narration(tmp_path):
    text = " ".join(f"Sentence number {i} explains one DNS step." for i in range(1, 21))
    provider, runner, job = setup(
        tmp_path,
        [{"scenes": [card(1, 4), card(5, 8), card(9, 16)]}]
        + [{"scenes": [card(17, 20)]}],
    )
    complete(job, "script", {"text": text, "claim_ids": ["c1"], "provenance": {}})
    with pytest.raises(ValueError, match="1-4 sentences"):
        # The chunk schema rejects a 9–16 span (the child repairs it in real runs).
        asyncio.run(provider.execute("storyboard", job))

    runner.outputs = iter(
        [
            {"scenes": [card(1, 4), card(5, 8), card(9, 12), card(13, 16)]},
            {"scenes": [card(17, 18), card(19, 20)]},
        ]
    )
    runner.calls.clear()
    result = asyncio.run(provider.execute("storyboard", job))
    # One model load, one request per 16-sentence chunk; the model never sees
    # or re-emits a whole script.
    ((role, payload),) = runner.calls
    assert role == "quality" and len(payload["requests"]) == 2
    assert {r["schema_name"] for r in payload["requests"]} == {"StoryboardChunk"}
    second = json.loads(payload["requests"][1]["messages"][1]["content"])
    assert [s["n"] for s in second["sentences"]] == [17, 18, 19, 20]
    scenes = result["scenes"]
    assert [s["scene_id"] for s in scenes] == [f"scene_{i:03d}" for i in range(1, 7)]
    assert " ".join(s["narration_text"] for s in scenes) == text
    assert scenes[0]["duration_seconds"] == round(28 / 2.5, 1)

    runner.outputs = iter(
        [
            {"scenes": [card(1, 4), card(5, 8), card(9, 12), card(13, 15)]},
            {"scenes": [card(17, 20)]},
        ]
    )
    with pytest.raises(ReviewRequired, match="sentences 1-16"):
        asyncio.run(provider.execute("storyboard", job))


def test_script_is_written_per_outline_section_and_stitched(tmp_path):
    provider, runner, job = setup(
        tmp_path,
        [
            {"text": words(30, "a"), "claim_ids": ["c1"]},
            {"text": words(30, "b"), "claim_ids": ["c2"]},
            {"text": words(30, "c"), "claim_ids": ["c1", "c2"]},
        ],
    )
    verified = [{"id": "c1", "text": "DNS"}, {"id": "c2", "text": "TTL"}]
    complete(job, "verification", {"verified_claims": verified})
    outline = [
        section("Intro", 40, ["c1"]),
        section("TTL", 40, ["c2"]),
        section("Wrap", 40, ["c1", "c2"]),
    ]
    complete(job, "outline", {"sections": outline})
    result = asyncio.run(provider.execute("script", job))
    # One model load, one request per section, nothing re-emitted.
    assert len(runner.calls) == 1
    requests = runner.calls[0][1]["requests"]
    assert [r["schema_name"] for r in requests] == ["ScriptSection"] * 3
    payloads = [json.loads(r["messages"][1]["content"]) for r in requests]
    assert [p["section_number"] for p in payloads] == [1, 2, 3]
    assert all(p["section_count"] == 3 for p in payloads)
    assert payloads[1]["section"]["target_words"] == int(40 * 2.5)
    assert [c["id"] for c in payloads[1]["verified_claims"]] == ["c2"]
    assert [o["title"] for o in payloads[0]["outline"]] == ["Intro", "TTL", "Wrap"]
    assert result["text"] == "\n\n".join(
        [words(30, "a"), words(30, "b"), words(30, "c")]
    )
    assert result["claim_ids"] == ["c1", "c2"]
    assert [s["title"] for s in result["sections"]] == ["Intro", "TTL", "Wrap"]


def test_short_section_is_retried_once_then_fails_closed(tmp_path):
    provider, runner, job = setup(
        tmp_path,
        [
            {"text": words(40), "claim_ids": ["c1"]},
            {"text": words(7), "claim_ids": ["c1"]},
            {"text": words(8), "claim_ids": ["c1"]},
        ],
    )
    complete(job, "verification", {"verified_claims": [{"id": "c1", "text": "DNS"}]})
    complete(job, "outline", {"sections": [section("A", 60), section("B", 600)]})
    with pytest.raises(ReviewRequired, match="Section 2 'B' has 8 words"):
        asyncio.run(provider.execute("script", job))
    assert [len(payload["requests"]) for _, payload in runner.calls] == [2, 1]
    retry = json.loads(runner.calls[1][1]["requests"][0]["messages"][1]["content"])
    assert retry["section_number"] == 2
    assert retry["previous_attempt_words"] == 7
    assert "1500 words" in retry["note"]


def test_short_section_retry_succeeds(tmp_path):
    provider, runner, job = setup(
        tmp_path,
        [
            {"text": words(40), "claim_ids": ["c1"]},
            {"text": words(7), "claim_ids": ["c1"]},
            {"text": words(400, "long"), "claim_ids": ["c1"]},
        ],
    )
    complete(job, "verification", {"verified_claims": [{"id": "c1", "text": "DNS"}]})
    complete(job, "outline", {"sections": [section("A", 60), section("B", 600)]})
    result = asyncio.run(provider.execute("script", job))
    assert [len(payload["requests"]) for _, payload in runner.calls] == [2, 1]
    assert result["sections"][1]["text"] == words(400, "long")


def test_script_requires_an_outline(tmp_path):
    provider, runner, job = setup(tmp_path, [])
    complete(job, "verification", {"verified_claims": [{"id": "c1", "text": "DNS"}]})
    with pytest.raises(ReviewRequired, match="outline"):
        asyncio.run(provider.execute("script", job))
    assert runner.calls == []


def test_critique_rewrites_each_draft_section(tmp_path):
    failing = {
        "score": 4,
        "issues": [],
        "required_changes": ["tighten"],
        "optional_changes": [],
    }
    passing = {"score": 9, "issues": [], "required_changes": [], "optional_changes": []}
    provider, runner, job = setup(
        tmp_path,
        [deepcopy(failing) for _ in range(5)]
        + [
            {"text": words(30, "x"), "claim_ids": ["c1"]},
            {"text": words(30, "y"), "claim_ids": ["c1"]},
        ]
        + [deepcopy(passing) for _ in range(5)],
    )
    provider.config.governor.critique_rounds = 2
    complete(job, "verification", {"verified_claims": [{"id": "c1", "text": "DNS"}]})
    complete(job, "outline", {"sections": [section("A", 20), section("B", 20)]})
    complete(
        job,
        "script",
        {
            "text": "One.\n\nTwo.",
            "claim_ids": ["c1"],
            "sections": [
                {"title": "A", "text": "One.", "claim_ids": ["c1"]},
                {"title": "B", "text": "Two.", "claim_ids": ["c1"]},
            ],
        },
    )
    result = asyncio.run(provider.execute("critique", job))
    assert [len(payload["requests"]) for _, payload in runner.calls] == [5, 2, 5]
    rewrite = [
        json.loads(r["messages"][1]["content"]) for r in runner.calls[1][1]["requests"]
    ]
    assert [r["draft"]["text"] for r in rewrite] == ["One.", "Two."]
    assert all("tighten" in json.dumps(r["required_changes"]) for r in rewrite)
    assert result["approved_script"]["text"] == words(30, "x") + "\n\n" + words(30, "y")
    assert [s["title"] for s in result["approved_script"]["sections"]] == ["A", "B"]


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
