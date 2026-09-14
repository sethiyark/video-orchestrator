"""Deterministic topic scoring. Component scores are supplied by providers, not an LLM vote."""

from pydantic import BaseModel, ConfigDict, Field

REQUIRED_COMPONENTS = (
    "search_demand",
    "competition",
    "evergreen_score",
    "channel_fit",
    "novelty_score",
    "visual_potential",
    "researchability",
    "predicted_retention",
)


class TopicComponents(BaseModel):
    model_config = ConfigDict(extra="forbid")
    search_demand: float = Field(ge=0, le=1)
    competition: float = Field(ge=0, le=1)
    evergreen_score: float = Field(ge=0, le=1)
    channel_fit: float = Field(ge=0, le=1)
    novelty_score: float = Field(ge=0, le=1)
    visual_potential: float = Field(ge=0, le=1)
    researchability: float = Field(ge=0, le=1)
    predicted_retention: float = Field(ge=0, le=1)


class TopicOpportunity(TopicComponents):
    topic: str = Field(min_length=1, max_length=200)
    angle: str = Field(min_length=1, max_length=400)
    opportunity_score: float = Field(ge=0, le=1)


def normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    missing = [name for name in REQUIRED_COMPONENTS if name not in weights]
    extra = [name for name in weights if name not in REQUIRED_COMPONENTS]
    if missing or extra:
        raise ValueError(
            f"Opportunity weights must match components; {missing=} {extra=}"
        )
    if any(value < 0 for value in weights.values()):
        raise ValueError("Opportunity weights must be >= 0")
    total = sum(weights.values())
    if total <= 0:
        raise ValueError("Opportunity weights must sum to a positive number")
    return {name: value / total for name, value in weights.items()}


def opportunity_score(components: TopicComponents, weights: dict[str, float]) -> float:
    normalized = normalize_weights(weights)
    raw = (
        components.search_demand * normalized["search_demand"]
        + (1.0 - components.competition) * normalized["competition"]
        + components.evergreen_score * normalized["evergreen_score"]
        + components.channel_fit * normalized["channel_fit"]
        + components.novelty_score * normalized["novelty_score"]
        + components.visual_potential * normalized["visual_potential"]
        + components.researchability * normalized["researchability"]
        + components.predicted_retention * normalized["predicted_retention"]
    )
    return round(min(1.0, max(0.0, raw)), 4)


def scored_opportunity(
    topic: str, angle: str, components: TopicComponents, weights: dict[str, float]
) -> TopicOpportunity:
    return TopicOpportunity(
        topic=topic,
        angle=angle,
        opportunity_score=opportunity_score(components, weights),
        **components.model_dump(),
    )
