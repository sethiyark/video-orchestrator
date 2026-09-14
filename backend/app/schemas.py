"""Bounded model outputs. Scene instructions contain data, never executable code."""

import re
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    model_validator,
)

# Chain-of-thought written into a JSON string instead of the answer: think tags,
# a planning opener, or the model narrating the request back in its first lines.
REASONING_LEAK = re.compile(
    r"</?think>"
    r"|^\s*(okay|ok|alright|hmm|so)\b[\s,.!]*(let me|i need|i'll|i will|i should)\b"
    r"|^\s*(let me|i need to|first, i)\b"
    r"|^.{0,300}\b(the|this) (user|query|request) (provided|asked|requested|is asking|has provided)\b",
    re.IGNORECASE | re.DOTALL,
)


def reject_reasoning(text: str) -> str:
    if REASONING_LEAK.search(text):
        raise ValueError(
            "text contains model reasoning instead of the requested content; "
            "return only the final content"
        )
    return text


Prose = Annotated[str, AfterValidator(reject_reasoning)]
# Short list items keep critic output bounded; the grammar enforces these.
Note = Annotated[Prose, Field(max_length=300)]


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
    summary: Prose = Field(max_length=2000)
    claims: list[Claim] = Field(min_length=1, max_length=30)


class Verdict(StrictModel):
    claim_id: str
    supported: bool
    confidence: float = Field(ge=0, le=1)
    reason: str = Field(max_length=600)


class Verification(StrictModel):
    verdicts: list[Verdict] = Field(min_length=1, max_length=30)


class Section(StrictModel):
    title: str = Field(max_length=160)
    purpose: str = Field(max_length=400)
    claim_ids: list[str] = Field(min_length=1)
    estimated_seconds: float = Field(gt=0, le=180)


class Outline(StrictModel):
    sections: list[Section] = Field(min_length=1, max_length=15)


class Script(StrictModel):
    text: Prose = Field(min_length=30, max_length=30000)
    claim_ids: list[str] = Field(min_length=1)


class ScriptSection(StrictModel):
    """Model output for one outline section; the provider joins sections."""

    text: Prose = Field(min_length=30, max_length=4000)
    claim_ids: list[str] = Field(min_length=1)


class Critic(StrictModel):
    score: float = Field(ge=0, le=10)
    issues: list[Note] = Field(max_length=6)
    required_changes: list[Note] = Field(max_length=6)
    optional_changes: list[Note] = Field(max_length=6)


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


class SeriesAssetProps(StrictModel):
    title: str = Field(max_length=160)
    asset_id: str = Field(min_length=1, max_length=36)
    caption: str = Field(default="", max_length=300)


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


class SeriesAssetScene(SceneBase):
    """Shows an existing series image/logo by id; the id is validated, never a path."""

    component: Literal["SeriesAsset"]
    props: SeriesAssetProps


Scene = Annotated[
    CardScene | FlowScene | BulletScene | ImageScene | SeriesAssetScene,
    Field(discriminator="component"),
]


class Storyboard(StrictModel):
    scenes: list[Scene] = Field(min_length=1, max_length=120)


class SentenceSpan(StrictModel):
    """Script sentences a planned scene narrates, by the 1-based numbers supplied."""

    first_sentence: int = Field(ge=1)
    last_sentence: int = Field(ge=1)


class CardPlan(SentenceSpan):
    component: Literal["DefinitionCard"]
    props: CardProps


class FlowPlan(SentenceSpan):
    component: Literal["AnimatedFlowDiagram"]
    props: FlowProps


class BulletPlan(SentenceSpan):
    component: Literal["BulletReveal"]
    props: BulletProps


class ImagePlan(SentenceSpan):
    component: Literal["ImagePan"]
    props: ImageProps


class SeriesAssetPlan(SentenceSpan):
    component: Literal["SeriesAsset"]
    props: SeriesAssetProps


PlannedScene = Annotated[
    CardPlan | FlowPlan | BulletPlan | ImagePlan | SeriesAssetPlan,
    Field(discriminator="component"),
]

MAX_SCENE_SENTENCES = 6


class StoryboardChunk(StrictModel):
    """Model output for one slice of the script. The provider copies narration
    text and assigns scene ids, so the model never re-emits the script."""

    scenes: list[PlannedScene] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def contiguous(self):
        previous = None
        for scene in self.scenes:
            span = scene.last_sentence - scene.first_sentence + 1
            if not 1 <= span <= MAX_SCENE_SENTENCES:
                raise ValueError(
                    f"each scene must cover 1-{MAX_SCENE_SENTENCES} sentences "
                    f"(got {scene.first_sentence}-{scene.last_sentence})"
                )
            if previous is not None and scene.first_sentence != previous + 1:
                raise ValueError(
                    "scenes must cover consecutive sentences with no gaps or overlaps"
                )
            previous = scene.last_sentence
        return self


class Metadata(StrictModel):
    title: str = Field(min_length=1, max_length=100)
    description: Prose = Field(max_length=5000)
    tags: list[Annotated[str, Field(max_length=100)]] = Field(max_length=20)
