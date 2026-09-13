"""Deterministic channel policy. Logical agents cannot mutate this object."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

HumanGate = Literal[
    "copyright_claim",
    "youtube_policy_warning",
    "channel_strategy_change",
    "delete_published_video",
    "factual_confidence_below_hard_threshold",
]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ChannelSection(Strict):
    slug: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=160)
    language: str = Field(default="en", min_length=2, max_length=12)
    niche: str = Field(default="technology_engineering", max_length=80)
    max_long_videos_per_week: int = Field(default=3, ge=0, le=14)
    max_shorts_per_week: int = Field(default=6, ge=0, le=28)


class ContentSection(Strict):
    min_research_confidence: float = Field(default=0.9, ge=0, le=1)
    min_script_score: float = Field(default=8.5, ge=0, le=10)
    min_originality_score: float = Field(default=0.85, ge=0, le=1)
    max_similarity_score: float = Field(default=0.6, ge=0, le=1)


class AutomationSection(Strict):
    autonomous_publish: bool = False


class CommentsSection(Strict):
    automatic_reply: bool = False


class ExternalLlmSection(Strict):
    enabled: bool = False
    provider: str = "openai"
    max_daily_cost_usd: float = Field(default=2.0, ge=0)


class BudgetSection(Strict):
    max_llm_attempts_per_stage: int = Field(default=3, ge=1, le=8)
    max_image_generations_per_video: int = Field(default=20, ge=0, le=100)
    max_external_api_cost_per_day_usd: float = Field(default=0.0, ge=0)
    max_external_api_cost_per_video_usd: float = Field(default=0.0, ge=0)


class ObservabilitySection(Strict):
    log_format: Literal["json", "text"] = "json"


class ChannelGovernor(Strict):
    channel: ChannelSection
    content: ContentSection = Field(default_factory=ContentSection)
    automation: AutomationSection = Field(default_factory=AutomationSection)
    comments: CommentsSection = Field(default_factory=CommentsSection)
    external_llm: ExternalLlmSection = Field(default_factory=ExternalLlmSection)
    budgets: BudgetSection = Field(default_factory=BudgetSection)
    human_required: list[HumanGate] = Field(min_length=1)
    observability: ObservabilitySection = Field(default_factory=ObservabilitySection)
    opportunity_weights: dict[str, float] = Field(min_length=1)

    def requires_human(self, gate: str) -> bool:
        return gate in self.human_required

    def may_publish_without_human(self) -> bool:
        return self.automation.autonomous_publish

    def may_auto_reply(self) -> bool:
        return self.comments.automatic_reply

    def may_use_external_llm(self) -> bool:
        return self.external_llm.enabled

    def allow_long_form(self, published_this_week: int) -> bool:
        if published_this_week < 0:
            raise ValueError("published_this_week must be >= 0")
        return published_this_week < self.channel.max_long_videos_per_week

    def allow_short(self, published_this_week: int) -> bool:
        if published_this_week < 0:
            raise ValueError("published_this_week must be >= 0")
        return published_this_week < self.channel.max_shorts_per_week

    def allow_attempt(self, attempt_index: int) -> bool:
        return 0 <= attempt_index < self.budgets.max_llm_attempts_per_stage

    def script_passes(self, score: float, required_changes: list[str]) -> bool:
        return score >= self.content.min_script_score and not required_changes

    def research_passes(self, confidence: float) -> bool:
        return confidence >= self.content.min_research_confidence

    def similarity_passes(self, overall: float) -> bool:
        return overall <= self.content.max_similarity_score

    def debit_allowed(self, spent_today_usd: float, additional_usd: float) -> bool:
        if additional_usd < 0 or spent_today_usd < 0:
            raise ValueError("costs must be >= 0")
        cap = self.budgets.max_external_api_cost_per_day_usd
        if self.external_llm.enabled:
            cap = max(cap, self.external_llm.max_daily_cost_usd)
        return spent_today_usd + additional_usd <= cap
