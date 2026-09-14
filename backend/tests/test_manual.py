import json

import pytest

from app.manual import compose_prompt, parse_payload
from app.schemas import ScriptSection


def test_compose_prompt_covers_every_request_in_order():
    requests = [
        ("Write section one.", {"title": "Intro"}, ScriptSection),
        ("Write section two.", {"title": "Wrap"}, ScriptSection),
    ]
    prompt = compose_prompt("SYSTEM.", requests)
    assert prompt.index("Write section one.") < prompt.index("Write section two.")
    assert prompt.count("ScriptSection") >= 2
    assert "JSON array of exactly 2" in prompt


def test_parse_payload_round_trips_valid_response():
    payload = json.dumps(
        [{"text": "A sufficiently long narration section.", "claim_ids": ["c1"]}]
    )
    result = parse_payload(payload, ["ScriptSection"])
    assert result == [
        {"text": "A sufficiently long narration section.", "claim_ids": ["c1"]}
    ]


def test_parse_payload_strips_markdown_fence():
    payload = "```json\n" + json.dumps([{"score": 9, "issues": [], "required_changes": [], "optional_changes": []}]) + "\n```"
    result = parse_payload(payload, ["Critic"])
    assert result[0]["score"] == 9


def test_parse_payload_rejects_invalid_json():
    with pytest.raises(ValueError, match="not valid JSON"):
        parse_payload("not json", ["ScriptSection"])


def test_parse_payload_rejects_non_array():
    with pytest.raises(ValueError, match="must be a JSON array"):
        parse_payload(json.dumps({"text": "x"}), ["ScriptSection"])


def test_parse_payload_rejects_wrong_length():
    payload = json.dumps([{"text": "x" * 40, "claim_ids": ["c1"]}])
    with pytest.raises(ValueError, match="1 item.*2 were expected"):
        parse_payload(payload, ["ScriptSection", "ScriptSection"])


def test_parse_payload_rejects_unknown_schema_name():
    with pytest.raises(ValueError, match="Unknown schema"):
        parse_payload(json.dumps([{}]), ["NotARealSchema"])


def test_parse_payload_rejects_schema_validation_failure():
    payload = json.dumps([{"text": "too short", "claim_ids": []}])
    with pytest.raises(ValueError, match="failed ScriptSection validation"):
        parse_payload(payload, ["ScriptSection"])

