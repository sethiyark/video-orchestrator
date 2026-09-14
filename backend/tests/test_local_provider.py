import asyncio
import json
from copy import deepcopy

import pytest

from app.config import Settings
from app.local_provider import LocalProvider, ManualStepRequired, ReviewRequired
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
    # Quote marks and commas are not evidence; single vs double is ignored too.
    assert (
        locate_quote("the study 'Grind size' found that", excerpt)
        == "The study \u201cGrind size\u201d found\u00a0that"
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
    with pytest.raises(ReviewRequired, match="revision budget") as failure:
        asyncio.run(provider.execute("critique", job))
    # The worker may send the job back to script with the blocking changes.
    assert failure.value.rewind_to == "script"
    assert failure.value.details["required_changes"] == {
        name: ["revise"]
        for name in ("accuracy", "retention", "clarity", "originality", "style")
    }
    assert failure.value.details["score"] == 4
    assert failure.value.details["review_artifact"]["id"].endswith(".json")
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
    import wave

    with wave.open(str(audio), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24000)
        wav.writeframes(b"\x00\x00" * 24000)
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
            "segments": [{"text": "DNS maps names to addresses.", "start": 0, "end": 1}],
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
    with pytest.raises(ReviewRequired, match="fidelity"):
        asyncio.run(provider.execute("render", job))


def card(first, last):
    return {
        "first_sentence": first,
        "last_sentence": last,
        "component": "DefinitionCard",
        "props": {"title": "DNS", "body": "Names to addresses"},
        "image_prompt": "A labeled diagram of a DNS lookup",
    }


def outro(first, last):
    return {
        "first_sentence": first,
        "last_sentence": last,
        "component": "Outro",
        "props": {"title": "Recap", "takeaways": ["Names map to addresses"]},
        "image_prompt": "A calm closing illustration of a network",
    }


def chapters(*spans):
    return {
        "chapters": [
            {
                "first_sentence": first,
                "last_sentence": last,
                "title": f"Chapter {index + 1}",
                "tagline": "One idea",
                "hero_prompt": "A wide illustration of resolvers talking",
            }
            for index, (first, last) in enumerate(spans)
        ]
    }


def test_storyboard_plans_sentence_chunks_and_copies_narration(tmp_path):
    text = " ".join(f"Sentence number {i} explains one DNS step." for i in range(1, 21))
    provider, runner, job = setup(
        tmp_path,
        [chapters((1, 20))]
        + [{"scenes": [card(1, 4), card(5, 8), card(9, 16)]}]
        + [{"scenes": [outro(17, 20)]}],
    )
    complete(job, "script", {"text": text, "claim_ids": ["c1"], "provenance": {}})
    with pytest.raises(ValueError, match="1-6 sentences"):
        # The chunk schema rejects a 9–16 span (the child repairs it in real runs).
        asyncio.run(provider.execute("storyboard", job))

    runner.outputs = iter(
        [
            chapters((1, 20)),
            {"scenes": [card(1, 4), card(5, 8), card(9, 12), card(13, 16)]},
            {"scenes": [card(17, 18), outro(19, 20)]},
        ]
    )
    runner.calls.clear()
    result = asyncio.run(provider.execute("storyboard", job))
    # Two model loads: one chapter plan over every sentence, then one request
    # per 16-sentence chunk; the model never re-emits a whole script.
    (plan_role, plan), (role, payload) = runner.calls
    assert plan_role == "quality" and len(plan["requests"]) == 1
    assert plan["requests"][0]["schema_name"] == "ChapterPlan"
    assert role == "quality" and len(payload["requests"]) == 2
    assert {r["schema_name"] for r in payload["requests"]} == {"StoryboardChunk"}
    second = json.loads(payload["requests"][1]["messages"][1]["content"])
    assert [s["n"] for s in second["sentences"]] == [17, 18, 19, 20]
    assert second["chapter"]["title"] == "Chapter 1"
    assert "CodeBlock" in second["available_components"]
    scenes = result["scenes"]
    assert [s["scene_id"] for s in scenes] == [f"scene_{i:03d}" for i in range(1, 7)]
    assert " ".join(s["narration_text"] for s in scenes) == text
    assert scenes[0]["duration_seconds"] == round(28 / 2.5, 1)
    assert result["chapters"] == [
        {
            "chapter_id": "chapter_01",
            "title": "Chapter 1",
            "tagline": "One idea",
            "first_scene": "scene_001",
            "last_scene": "scene_006",
            "hero_prompt": "A wide illustration of resolvers talking",
            "accent": 0,
        }
    ]
    # Images are disabled in the default profile: prompts are dropped.
    assert all(scene["image_prompt"] == "" for scene in scenes)

    # Off-by-one boundaries are snapped, not rejected: an overlap (5-8 then
    # 8-12) trims the later scene, a gap (12 then 14) and a short tail (15)
    # are absorbed, and a scene left with nothing to narrate is dropped.
    runner.outputs = iter(
        [
            chapters((1, 20)),
            {
                "scenes": [
                    card(1, 4),
                    card(5, 8),
                    card(8, 12),
                    card(14, 15),
                    card(9, 10),
                ]
            },
            {"scenes": [outro(18, 20)]},
        ]
    )
    result = asyncio.run(provider.execute("storyboard", job))
    scenes = result["scenes"]
    assert [s["scene_id"] for s in scenes] == [f"scene_{i:03d}" for i in range(1, 6)]
    assert " ".join(s["narration_text"] for s in scenes) == text
    assert scenes[3]["narration_text"].startswith("Sentence number 13 ")
    assert scenes[3]["narration_text"].endswith(
        "Sentence number 16 explains one DNS step."
    )
    assert scenes[4]["narration_text"].startswith("Sentence number 17 ")

    # A plan that lies entirely outside its chunk (the model restarted its
    # numbering) is still a review error.
    runner.outputs = iter(
        [
            chapters((1, 20)),
            {"scenes": [card(1, 4), card(5, 8), card(9, 12), card(13, 16)]},
            {"scenes": [outro(1, 4)]},
        ]
    )
    with pytest.raises(ReviewRequired, match="sentences 17-20"):
        asyncio.run(provider.execute("storyboard", job))


def test_storyboard_chunks_never_cross_chapters(tmp_path):
    text = " ".join(f"Sentence number {i} explains one DNS step." for i in range(1, 21))
    provider, runner, job = setup(
        tmp_path,
        [
            chapters((1, 6), (7, 20)),
            {"scenes": [card(1, 3), card(4, 6)]},
            {"scenes": [card(7, 12), card(13, 18), outro(19, 20)]},
        ],
    )
    complete(job, "script", {"text": text, "claim_ids": ["c1"], "provenance": {}})
    result = asyncio.run(provider.execute("storyboard", job))
    payload = runner.calls[1][1]
    spans = [
        [s["n"] for s in json.loads(r["messages"][1]["content"])["sentences"]]
        for r in payload["requests"]
    ]
    assert spans == [list(range(1, 7)), list(range(7, 21))]
    assert [(c["first_scene"], c["last_scene"], c["accent"]) for c in result["chapters"]] == [
        ("scene_001", "scene_002", 0),
        ("scene_003", "scene_005", 1),
    ]


def test_storyboard_falls_back_to_outline_sections_when_too_long(tmp_path):
    text = " ".join(f"Sentence number {i} explains one DNS step." for i in range(1, 9))
    provider, runner, job = setup(
        tmp_path,
        [{"scenes": [card(1, 4)]}, {"scenes": [outro(5, 8)]}],
    )
    complete(
        job,
        "script",
        {
            "text": text,
            "claim_ids": ["c1"],
            "sections": [
                {"title": "Basics", "text": " ".join(text.split(". ")[:4]) + ".", "claim_ids": ["c1"]},
                {"title": "Caching", "text": " ".join(text.split(". ")[4:]), "claim_ids": ["c1"]},
            ],
        },
    )
    real_budget = provider.budget

    def budget(stage, data):
        # Only the whole-script chapter request is over budget here.
        if "outline" in data:
            raise ReviewRequired("storyboard input exceeds the model context budget")
        real_budget(stage, data)

    provider.budget = budget
    result = asyncio.run(provider.execute("storyboard", job))
    assert [c["title"] for c in result["chapters"]] == ["Basics", "Caching"]
    assert all(r["schema_name"] == "StoryboardChunk" for r in runner.calls[0][1]["requests"])


def test_storyboard_structure_rules_rewind(tmp_path):
    text = "First sentence here. Second sentence here. Third sentence here."
    provider, runner, job = setup(tmp_path, [])
    complete(job, "script", {"text": text, "claim_ids": ["c1"], "provenance": {}})
    complete(
        job,
        "verification",
        {
            "verified_claims": [
                {
                    "id": "c1",
                    "text": "DNS",
                    "source_id": "s1",
                    "quote": "DNS maps domain names to IP addresses.",
                }
            ]
        },
    )

    def run(*scenes):
        runner.outputs = iter([chapters((1, 3)), {"scenes": list(scenes)}])
        return asyncio.run(provider.execute("storyboard", job))

    with pytest.raises(ReviewRequired, match="must be an Outro") as info:
        run(card(1, 2), card(3, 3))
    assert info.value.rewind_to == "storyboard"
    with pytest.raises(ReviewRequired, match="Outro before the final"):
        run(outro(1, 2), outro(3, 3))
    title = {**card(1, 1), "component": "ChapterTitle", "props": {"title": "DNS"}}
    with pytest.raises(ReviewRequired, match="ChapterTitle outside"):
        run(card(1, 1), {**title, "first_sentence": 2, "last_sentence": 2}, outro(3, 3))
    callout = {
        **card(2, 2),
        "component": "Callout",
        "props": {"title": "Quote", "quote": "made up words", "claim_id": "c1"},
    }
    with pytest.raises(ReviewRequired, match="not inside its verified claim"):
        run(title, callout, outro(3, 3))
    callout["props"]["quote"] = "maps domain names to IP"
    result = run(title, callout, outro(3, 3))
    assert [s["component"] for s in result["scenes"]] == ["ChapterTitle", "Callout", "Outro"]

    provider.settings.models.images_enabled = True
    try:
        with pytest.raises(ReviewRequired, match="missing an image_prompt"):
            run(title, {**card(2, 2), "image_prompt": ""}, outro(3, 3))
        picture = {
            **card(2, 2),
            "component": "ImagePan",
            "props": {"title": "Lookup", "prompt": "A labeled diagram of a DNS lookup path"},
            "image_prompt": "",
        }
        result = run(title, picture, outro(3, 3))
        # ImagePan's own prompt doubles as its image prompt.
        assert result["scenes"][1]["image_prompt"] == "A labeled diagram of a DNS lookup path"
        assert result["scenes"][0]["image_prompt"] == card(1, 1)["image_prompt"]
        assert "Every scene needs a concrete image_prompt" in json.dumps(runner.calls[-1][1])
    finally:
        provider.settings.models.images_enabled = False


def test_worker_retry_attempt_shifts_default_llm_seed(tmp_path):
    """A worker-level retry (main.py's attempt index) must not silently replay the
    same deterministic request: local inference uses a fixed seed, so an
    unvaried retry of a validation failure reproduces the identical bad output
    every time instead of giving the model a real second chance."""
    text = " ".join(f"Sentence number {i} explains one DNS step." for i in range(1, 5))
    provider, runner, job = setup(
        tmp_path, [chapters((1, 4)), {"scenes": [outro(1, 4)]}]
    )
    complete(job, "script", {"text": text, "claim_ids": ["c1"], "provenance": {}})
    asyncio.run(provider.execute("storyboard", job, attempt=0))
    seed_attempt_0 = runner.calls[0][1]["requests"][0]["seed"]

    runner.outputs = iter([chapters((1, 4)), {"scenes": [outro(1, 4)]}])
    runner.calls.clear()
    asyncio.run(provider.execute("storyboard", job, attempt=2))
    seed_attempt_2 = runner.calls[0][1]["requests"][0]["seed"]

    assert seed_attempt_0 == 42
    assert seed_attempt_2 == 44
    assert seed_attempt_0 != seed_attempt_2


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


def test_script_rewrites_from_critique_corrections(tmp_path):
    provider, runner, job = setup(
        tmp_path,
        [
            {"text": words(30, "a"), "claim_ids": ["c1"]},
            {"text": words(30, "b"), "claim_ids": ["c1"]},
        ],
    )
    complete(job, "verification", {"verified_claims": [{"id": "c1", "text": "DNS"}]})
    complete(job, "outline", {"sections": [section("Intro", 40), section("Wrap", 40)]})
    last_draft = {
        "text": "Old intro.\n\nOld wrap.",
        "claim_ids": ["c1"],
        "sections": [
            {"title": "Intro", "text": "Old intro.", "claim_ids": ["c1"]},
            {"title": "Wrap", "text": "Old wrap.", "claim_ids": ["c1"]},
        ],
    }
    review = provider.artifacts.put_json(job["id"], {"last_draft": last_draft})
    job["corrections"] = {
        "script": {
            "from_stage": "critique",
            "attempt": 1,
            "message": "Script did not pass independent critics",
            "review_artifact": review,
            "required_changes": {"clarity": ["Cut the repetition."]},
        }
    }
    result = asyncio.run(provider.execute("script", job))
    requests = runner.calls[0][1]["requests"]
    assert len(requests) == 2
    for index, request in enumerate(requests):
        assert "failed independent critics" in request["messages"][0]["content"]
        payload = json.loads(request["messages"][1]["content"])
        assert payload["required_changes"] == {"clarity": ["Cut the repetition."]}
        assert payload["previous_attempt"] == last_draft["sections"][index]["text"]
    assert result["sections"][1]["text"] == words(30, "b")


def test_script_without_corrections_keeps_its_prompt(tmp_path):
    provider, runner, job = setup(tmp_path, [{"text": words(30), "claim_ids": ["c1"]}])
    complete(job, "verification", {"verified_claims": [{"id": "c1", "text": "DNS"}]})
    complete(job, "outline", {"sections": [section("Intro", 40)]})
    asyncio.run(provider.execute("script", job))
    request = runner.calls[0][1]["requests"][0]
    assert "failed independent critics" not in request["messages"][0]["content"]
    payload = json.loads(request["messages"][1]["content"])
    assert "required_changes" not in payload and "previous_attempt" not in payload


def test_alignment_repairs_asr_text_using_validated_tts_segments(tmp_path):
    provider, _, job = narration_job(tmp_path, {
        "segments": [{"text": "DNS maps names to address", "start": 0, "end": 1}],
        "method": "asr_transcript", "fidelity": 0.99,
    })
    narration = next(s["output"] for s in job["stages"] if s["name"] == "narration")
    narration["segments"] = [{"text": narration["text"], "start": 0, "end": 1}]
    result = asyncio.run(provider.execute("alignment", job))
    assert result["segments"] == narration["segments"]
    assert result["timing_method"] == "tts_sentence_interpolation"
    assert result["fidelity"] == 0.99


@pytest.mark.parametrize("end", [1, 2])
def test_alignment_without_valid_repair_rewinds_narration(tmp_path, end):
    provider, _, job = narration_job(tmp_path, {
        "segments": [{"text": "wrong words", "start": 0, "end": end}],
        "fidelity": 0.99,
    })
    with pytest.raises(ReviewRequired, match="not renderable") as error:
        asyncio.run(provider.execute("alignment", job))
    assert error.value.rewind_to == "narration"


def test_validation_retry_prompt_includes_feedback_and_changes_seed(tmp_path):
    provider, runner, job = setup(tmp_path, [{"title": "DNS", "description": "DNS explained", "tags": ["DNS"]}])
    complete(job, "script", {"text": "DNS explained", "claim_ids": []})
    job["corrections"] = {"metadata": {"attempt": 1, "message": "Missing title"}}
    asyncio.run(provider.execute("metadata", job))
    request = runner.calls[0][1]["requests"][0]
    assert request["seed"] == 43
    assert json.loads(request["messages"][1]["content"])["validation_feedback"]["message"] == "Missing title"


def test_stale_storyboard_rewinds_to_storyboard(tmp_path):
    provider, _, job = narration_job(tmp_path, {
        "segments": [{"text": "DNS maps names to addresses.", "start": 0, "end": 1}],
        "fidelity": 1.0,
    })
    complete(job, "storyboard", {"scenes": [{"narration_text": "Old script."}]})
    with pytest.raises(ReviewRequired, match="Storyboard narration is stale") as error:
        asyncio.run(provider.execute("alignment", job))
    assert error.value.rewind_to == "storyboard"


def test_tts_timing_cannot_bypass_fidelity(tmp_path):
    provider, _, job = narration_job(tmp_path, {
        "segments": [{"text": "garbled", "start": 0, "end": 1}],
        "fidelity": 0.1,
    })
    narration = next(s["output"] for s in job["stages"] if s["name"] == "narration")
    narration["segments"] = [{"text": narration["text"], "start": 0, "end": 1}]
    with pytest.raises(ReviewRequired, match="fidelity") as error:
        asyncio.run(provider.execute("alignment", job))
    assert error.value.rewind_to == "narration"


def stage(job, name):
    return next(s for s in job["stages"] if s["name"] == name)


def test_manual_script_parks_with_combined_prompt_and_no_model_load(tmp_path):
    provider, runner, job = setup(tmp_path, [])
    provider.config.routes["script"] = "manual"
    complete(job, "verification", {"verified_claims": [{"id": "c1", "text": "DNS"}]})
    complete(
        job,
        "outline",
        {"sections": [section("Intro", 40, ["c1"]), section("Wrap", 40, ["c1"])]},
    )
    with pytest.raises(ManualStepRequired) as failure:
        asyncio.run(provider.execute("script", job))
    assert runner.calls == []
    assert "Intro" in failure.value.prompt
    assert "Wrap" in failure.value.prompt
    assert failure.value.schema_names == ["ScriptSection", "ScriptSection"]


def test_manual_script_resume_with_valid_pasted_response(tmp_path):
    provider, runner, job = setup(tmp_path, [])
    provider.config.routes["script"] = "manual"
    complete(job, "verification", {"verified_claims": [{"id": "c1", "text": "DNS"}]})
    complete(
        job,
        "outline",
        {"sections": [section("Intro", 40, ["c1"]), section("Wrap", 40, ["c1"])]},
    )
    pasted = json.dumps(
        [
            {"text": words(30, "a"), "claim_ids": ["c1"]},
            {"text": words(30, "b"), "claim_ids": ["c1"]},
        ]
    )
    stage(job, "script")["output"] = {"manual": {"responses": {"0": pasted}}}
    result = asyncio.run(provider.execute("script", job))
    assert runner.calls == []
    assert result["text"] == "\n\n".join([words(30, "a"), words(30, "b")])


def test_manual_script_resume_rejects_response_outside_verified_claims(tmp_path):
    provider, _runner, job = setup(tmp_path, [])
    provider.config.routes["script"] = "manual"
    complete(job, "verification", {"verified_claims": [{"id": "c1", "text": "DNS"}]})
    complete(job, "outline", {"sections": [section("Intro", 40, ["c1"])]})
    pasted = json.dumps([{"text": words(30, "a"), "claim_ids": ["invented"]}])
    stage(job, "script")["output"] = {"manual": {"responses": {"0": pasted}}}
    with pytest.raises(ReviewRequired, match="outside"):
        asyncio.run(provider.execute("script", job))


def test_manual_resume_rejects_malformed_cached_response(tmp_path):
    provider, runner, job = setup(tmp_path, [])
    provider.config.routes["script"] = "manual"
    complete(job, "verification", {"verified_claims": [{"id": "c1", "text": "DNS"}]})
    complete(job, "outline", {"sections": [section("Intro", 40, ["c1"])]})
    stage(job, "script")["output"] = {"manual": {"responses": {"0": "not json"}}}
    with pytest.raises(ValueError, match="not valid JSON"):
        asyncio.run(provider.execute("script", job))
    assert runner.calls == []


def test_manual_critique_single_round_resume_passes(tmp_path):
    provider, runner, job = setup(tmp_path, [])
    provider.config.routes["critique"] = "manual"
    passing = {"score": 9, "issues": [], "required_changes": [], "optional_changes": []}
    complete(job, "verification", {"verified_claims": [{"id": "c1", "text": "DNS"}]})
    complete(job, "script", {"text": "Draft", "claim_ids": ["c1"]})
    stage(job, "critique")["output"] = {
        "manual": {"responses": {"0": json.dumps([passing] * 5)}}
    }
    result = asyncio.run(provider.execute("critique", job))
    assert runner.calls == []
    assert result["score"] == 9


def test_manual_critique_low_score_parks_again_for_next_round(tmp_path):
    """Critique alone is manual; the rewrite it triggers (tagged "script")
    still runs locally since routes["script"] is untouched — confirming the
    two stages' manual-ness is independent, and that a second parked round
    correctly gets the next call index (1) rather than replaying round 1."""
    failing = {
        "score": 4,
        "issues": [],
        "required_changes": ["tighten"],
        "optional_changes": [],
    }
    rewrite = {"text": "A revised and sufficiently long draft.", "claim_ids": ["c1"]}
    provider, runner, job = setup(tmp_path, [rewrite])
    provider.config.routes["critique"] = "manual"
    provider.config.governor.critique_rounds = 2
    complete(job, "verification", {"verified_claims": [{"id": "c1", "text": "DNS"}]})
    complete(job, "script", {"text": "Draft", "claim_ids": ["c1"]})
    stage(job, "critique")["output"] = {
        "manual": {"responses": {"0": json.dumps([failing] * 5)}}
    }
    with pytest.raises(ManualStepRequired) as second_round:
        asyncio.run(provider.execute("critique", job))
    assert len(runner.calls) == 1  # only the local rewrite touched the model
    assert "step 2" in str(second_round.value)
