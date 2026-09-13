"""Bounded model outputs. Scene instructions contain data, never executable code."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Source(StrictModel):
    id: str = Field(min_length=1, max_length=80)
    url: HttpUrl
    title: str = Field(min_length=1, max_length=300)
    excerpt: str = Field(min_length=20, max_length=6000)


class Claim(StrictModel):
    id: str = Field(min_length=1, max_length=80)
    text: str = Field(min_length=1, max_length=1000)
    source_id: str
    quote: str = Field(min_length=10, max_length=2000)


class Research(StrictModel):
    summary: str = Field(max_length=2000)
    claims: list[Claim] = Field(min_length=1, max_length=30)


class Verdict(StrictModel):
    claim_id: str
    supported: bool
    confidence: float = Field(ge=0, le=1)
    reason: str


class Verification(StrictModel):
    verdicts: list[Verdict] = Field(min_length=1, max_length=30)


class Section(StrictModel):
    title: str
    purpose: str
    claim_ids: list[str] = Field(min_length=1)
    estimated_seconds: float = Field(gt=0, le=180)


class Outline(StrictModel):
    sections: list[Section] = Field(min_length=1, max_length=15)


class Script(StrictModel):
    text: str = Field(min_length=30, max_length=30000)
    claim_ids: list[str] = Field(min_length=1)


class Critic(StrictModel):
    score: float = Field(ge=0, le=10)
    issues: list[str]
    required_changes: list[str]
    optional_changes: list[str]


class CardProps(StrictModel):
    title: str = Field(max_length=160)
    body: str = Field(max_length=500)


class FlowProps(StrictModel):
    title: str = Field(max_length=160)
    nodes: list[str] = Field(min_length=2, max_length=8)


class BulletProps(StrictModel):
    title: str = Field(max_length=160)
    bullets: list[str] = Field(min_length=1, max_length=6)


class ImageProps(StrictModel):
    title: str = Field(max_length=160)
    prompt: str = Field(min_length=10, max_length=500)


class SceneBase(StrictModel):
    scene_id: str = Field(pattern=r"^scene_[0-9]{3}$")
    narration_text: str
    duration_seconds: float = Field(gt=0, le=60)


class CardScene(SceneBase):
    component: Literal["DefinitionCard"]
    props: CardProps


class FlowScene(SceneBase):
    component: Literal["AnimatedFlowDiagram"]
    props: FlowProps


class BulletScene(SceneBase):
    component: Literal["BulletReveal"]
    props: BulletProps


class ImageScene(SceneBase):
    component: Literal["ImagePan"]
    props: ImageProps


Scene = Annotated[
    CardScene | FlowScene | BulletScene | ImageScene, Field(discriminator="component")
]


class Storyboard(StrictModel):
    scenes: list[Scene] = Field(min_length=1, max_length=120)


class Metadata(StrictModel):
    title: str = Field(min_length=1, max_length=100)
    description: str = Field(max_length=5000)
    tags: list[str] = Field(max_length=20)
