import pytest

from app.config import ModelConfig, Settings


def test_manual_route_skips_model_requirement_for_llm_stages():
    data = Settings().models.model_dump()
    data["routes"]["script"] = "manual"
    data["routes"]["critique"] = "manual"
    ModelConfig.model_validate(data)  # no ValueError: no "manual" ModelSpec needed


def test_manual_route_still_requires_a_model_for_non_llm_stages():
    data = Settings().models.model_dump()
    data["routes"]["narration"] = "manual"
    with pytest.raises(ValueError, match="narration requires"):
        ModelConfig.model_validate(data)
