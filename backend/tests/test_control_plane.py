"""Control-plane unit tests for governor, scoring, workflow states, and object storage."""

import asyncio

from fastapi.testclient import TestClient

from app.config import Settings
from app.domain.scoring import TopicComponents, opportunity_score, scored_opportunity
from app.domain.states import IllegalStateTransition, VideoState, transition
from app.governor import ChannelGovernor
from app.main import create_app
from app.providers import MockProvider
from app.storage import LocalObjectStore


def test_governor_enforces_caps_and_human_gates():
    governor = Settings().channel_governor
    assert isinstance(governor, ChannelGovernor)
    assert not governor.may_publish_without_human()
    assert not governor.may_use_external_llm()
    assert not governor.may_auto_reply()
    assert governor.allow_long_form(2)
    assert not governor.allow_long_form(3)
    assert governor.allow_attempt(0)
    assert not governor.allow_attempt(3)
    assert governor.script_passes(8.5, [])
    assert not governor.script_passes(8.4, [])
    assert not governor.script_passes(10, ["fix hook"])
    assert governor.research_passes(0.9)
    assert not governor.similarity_passes(0.61)
    assert governor.debit_allowed(0, 0)
    assert not governor.debit_allowed(0, 0.01)
    assert governor.requires_human("copyright_claim")


def test_opportunity_score_is_deterministic_and_penalizes_competition():
    weights = Settings().channel_governor.opportunity_weights
    low_competition = TopicComponents(
        search_demand=0.8,
        competition=0.1,
        evergreen_score=0.9,
        channel_fit=0.9,
        novelty_score=0.7,
        visual_potential=0.8,
        researchability=0.9,
        predicted_retention=0.7,
    )
    high_competition = low_competition.model_copy(update={"competition": 0.9})
    low = opportunity_score(low_competition, weights)
    high = opportunity_score(high_competition, weights)
    assert low > high
    assert opportunity_score(low_competition, weights) == low
    topic = scored_opportunity(
        "DNS", "How resolvers actually work", low_competition, weights
    )
    assert topic.opportunity_score == low


def test_illegal_state_transitions_are_rejected():
    assert transition(VideoState.DISCOVERED, VideoState.SCORED) is VideoState.SCORED
    assert (
        transition(VideoState.SCRIPT_REVIEW, VideoState.SCRIPTING)
        is VideoState.SCRIPTING
    )
    try:
        transition(VideoState.PUBLISHED, VideoState.SCRIPTING)
        raise AssertionError("expected illegal transition")
    except IllegalStateTransition:
        pass


def test_health_and_system_and_metrics(tmp_path):
    with TestClient(create_app(str(tmp_path / "jobs.db"), MockProvider(0))) as client:
        health = client.get("/api/health").json()
        assert health["status"] == "ok"
        assert health["dependencies"]["database"] == "ok"
        assert health["dependencies"]["storage"] == "ok"
        assert health["dependencies"]["redis"] == "disabled"
        assert health["dependencies"]["temporal"] == "disabled"
        assert health["approval_required"] is True
        system = client.get("/api/system").json()
        assert system["automation"]["autonomous_publish"] is False
        assert system["channel"]["slug"] == "engineering-explainers"
        metrics = client.get("/metrics")
        assert metrics.status_code == 200
        assert b"python_info" in metrics.content or b"process_" in metrics.content


async def _put_and_get(tmp_path):
    store = LocalObjectStore(tmp_path / "objects")
    meta = await store.put("video/demo/script.json", b'{"ok":true}', "application/json")
    assert meta["sha256"]
    assert await store.exists("video/demo/script.json")
    assert await store.get("video/demo/script.json") == b'{"ok":true}'
    try:
        await store.put("../escape.json", b"no")
        raise AssertionError("expected path rejection")
    except ValueError:
        pass


def test_local_object_store_hashes_and_rejects_escape(tmp_path):
    asyncio.run(_put_and_get(tmp_path))
