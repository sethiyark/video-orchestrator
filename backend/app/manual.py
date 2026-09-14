"""Compose and parse the combined prompt/response pair for a manually-relayed
LLM call: a human pastes ``compose_prompt``'s output into their own Claude or
Gemini chat and pastes the reply back through ``parse_payload``. Both the API
endpoint (pre-accept validation) and ``LocalProvider`` (replay on resume) use
``parse_payload`` so they can never disagree about what counts as valid."""

from __future__ import annotations

import json

from pydantic import ValidationError

from .schemas import (
    Critic,
    Metadata,
    Outline,
    Research,
    ScriptSection,
    StoryboardChunk,
    Verification,
)

SCHEMAS = {
    schema.__name__: schema
    for schema in (Research, Verification, Outline, ScriptSection, Critic, StoryboardChunk, Metadata)
}


def compose_prompt(system_prompt: str, requests) -> str:
    """One prompt covering every (instructions, data, schema, *options) request,
    asking for a JSON array of exactly len(requests) items in the same order."""
    parts = [
        system_prompt.strip(),
        "",
        (
            f"You will receive {len(requests)} request(s) below. Reply with a single "
            f"JSON array of exactly {len(requests)} object(s), one per request, in "
            "the same order, each conforming to that request's schema. Return only "
            "the JSON array — no markdown code fences, no commentary before or "
            "after it."
        ),
    ]
    for index, (instructions, data, schema, *_) in enumerate(requests):
        parts.append(
            f"\n### Request {index + 1} of {len(requests)}: {schema.__name__}\n"
            f"Instructions: {instructions}\n"
            f"Schema: {json.dumps(schema.model_json_schema())}\n"
            f"Data:\n{json.dumps(data, indent=2)}"
        )
    return "\n".join(parts)


def _strip_fence(raw_text: str) -> str:
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        text = text.removesuffix("```")
    return text.strip()


def parse_payload(raw_text: str, schema_names: list[str]) -> list[dict]:
    """Validate a pasted reply against the schemas of the requests it answers.
    Raises ValueError with a specific reason on any mismatch."""
    text = _strip_fence(raw_text)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Response is not valid JSON: {exc}") from exc
    if not isinstance(payload, list):
        raise ValueError("Response must be a JSON array")  # noqa: TRY004 -- contract is ValueError-only
    if len(payload) != len(schema_names):
        raise ValueError(
            f"Response has {len(payload)} item(s) but {len(schema_names)} were expected"
        )
    results = []
    for index, (name, item) in enumerate(zip(schema_names, payload)):
        schema = SCHEMAS.get(name)
        if schema is None:
            raise ValueError(f"Unknown schema {name!r} for item {index + 1}")
        try:
            results.append(schema.model_validate(item).model_dump())
        except ValidationError as exc:
            raise ValueError(f"Item {index + 1} failed {name} validation: {exc}") from exc
    return results
