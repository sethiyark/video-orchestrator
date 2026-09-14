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


class ChapterTitleProps(StrictModel):
    title: str = Field(max_length=80)
    subtitle: str = Field(default="", max_length=160)


class OutroProps(StrictModel):
    title: str = Field(max_length=80)
    takeaways: list[Annotated[str, Field(max_length=120)]] = Field(
        min_length=1, max_length=4
    )
    next_topic: str = Field(default="", max_length=120)


# Display-only syntax classes for CodeBlock; the renderer tokenizes text, never runs it.
CodeLanguage = Literal[
    "python",
    "typescript",
    "javascript",
    "go",
    "rust",
    "bash",
    "sql",
    "yaml",
    "json",
    "c",
    "cpp",
    "java",
    "text",
]


class CodeBlockProps(StrictModel):
    title: str = Field(max_length=160)
    language: CodeLanguage = "text"
    code: str = Field(min_length=1, max_length=1200)
    highlight_lines: list[Annotated[int, Field(ge=1, le=40)]] = Field(
        default_factory=list, max_length=6
    )


class TerminalLine(StrictModel):
    kind: Literal["command", "output"] = "output"
    text: str = Field(max_length=120)


class TerminalProps(StrictModel):
    title: str = Field(max_length=160)
    lines: list[TerminalLine] = Field(min_length=1, max_length=12)


class ComparisonSide(StrictModel):
    label: str = Field(min_length=1, max_length=60)
    points: list[Annotated[str, Field(max_length=120)]] = Field(
        min_length=1, max_length=4
    )


class ComparisonProps(StrictModel):
    title: str = Field(max_length=160)
    left: ComparisonSide
    right: ComparisonSide


class Stat(StrictModel):
    value: str = Field(min_length=1, max_length=16)
    label: str = Field(min_length=1, max_length=60)


class StatCounterProps(StrictModel):
    title: str = Field(max_length=160)
    stats: list[Stat] = Field(min_length=1, max_length=4)


class TimelineEvent(StrictModel):
    label: str = Field(min_length=1, max_length=40)
    text: str = Field(max_length=120)


class TimelineProps(StrictModel):
    title: str = Field(max_length=160)
    events: list[TimelineEvent] = Field(min_length=2, max_length=6)


class CalloutProps(StrictModel):
    """A pull-quote. The provider requires ``quote`` to be located inside the
    verified claim ``claim_id`` cites; anything else fails closed."""

    title: str = Field(max_length=160)
    quote: str = Field(min_length=1, max_length=300)
    claim_id: str = Field(min_length=1, max_length=80)


# Closed icon vocabulary rendered as inline SVG by the renderer; never a URL.
IconName = Literal[
    "server",
    "database",
    "cloud",
    "lock",
    "key",
    "network",
    "cpu",
    "memory",
    "disk",
    "code",
    "terminal",
    "browser",
    "mobile",
    "user",
    "users",
    "clock",
    "bolt",
    "shield",
    "gear",
    "chart",
    "search",
    "mail",
    "globe",
    "warning",
]


class IconItem(StrictModel):
    icon: IconName
    label: str = Field(min_length=1, max_length=40)


class IconGridProps(StrictModel):
    title: str = Field(max_length=160)
    items: list[IconItem] = Field(min_length=2, max_length=6)


# component name → props schema. The renderer implements exactly these.
COMPONENT_PROPS = {
    "DefinitionCard": CardProps,
    "AnimatedFlowDiagram": FlowProps,
    "BulletReveal": BulletProps,
    "ImagePan": ImageProps,
    "SeriesAsset": SeriesAssetProps,
    "ChapterTitle": ChapterTitleProps,
    "Outro": OutroProps,
    "CodeBlock": CodeBlockProps,
    "Terminal": TerminalProps,
    "Comparison": ComparisonProps,
    "StatCounter": StatCounterProps,
    "Timeline": TimelineProps,
    "Callout": CalloutProps,
    "IconGrid": IconGridProps,
}
COMPONENTS = tuple(COMPONENT_PROPS)
SCENE_ID = r"^scene_[0-9]{3}$"
CHAPTER_ID = r"^chapter_[0-9]{2}$"
MAX_CHAPTERS = 12


class SceneBase(StrictModel):
    scene_id: str = Field(pattern=SCENE_ID)
    narration_text: str
    duration_seconds: float = Field(gt=0, le=60)
    # One generated (or relayed) image per scene: the plate behind text
    # components, the subject of ImagePan. Required by the provider when
    # images are enabled; optional in the schema for mock mode and old jobs.
    image_prompt: str = Field(default="", max_length=300)


class SentenceSpan(StrictModel):
    """Script sentences a planned scene narrates, by the 1-based numbers supplied."""

    first_sentence: int = Field(ge=1)
    last_sentence: int = Field(ge=1)
    image_prompt: str = Field(default="", max_length=300)


def _scene_classes(base, suffix):
    """One subclass of ``base`` per component, discriminated by ``component``."""
    classes = []
    for name, props in COMPONENT_PROPS.items():
        classes.append(
            type(
                f"{name}{suffix}",
                (base,),
                {
                    "__annotations__": {"component": Literal[name], "props": props},
                    "__module__": __name__,
                },
            )
        )
    return classes


# Assembled storyboard scenes (CardScene, FlowScene, ... by component name).
SCENE_CLASSES = _scene_classes(SceneBase, "Scene")
# Model-planned scenes over sentence numbers.
PLAN_CLASSES = _scene_classes(SentenceSpan, "Plan")

Scene = Annotated[
    SCENE_CLASSES[0]
    | SCENE_CLASSES[1]
    | SCENE_CLASSES[2]
    | SCENE_CLASSES[3]
    | SCENE_CLASSES[4]
    | SCENE_CLASSES[5]
    | SCENE_CLASSES[6]
    | SCENE_CLASSES[7]
    | SCENE_CLASSES[8]
    | SCENE_CLASSES[9]
    | SCENE_CLASSES[10]
    | SCENE_CLASSES[11]
    | SCENE_CLASSES[12]
    | SCENE_CLASSES[13],
    Field(discriminator="component"),
]
PlannedScene = Annotated[
    PLAN_CLASSES[0]
    | PLAN_CLASSES[1]
    | PLAN_CLASSES[2]
    | PLAN_CLASSES[3]
    | PLAN_CLASSES[4]
    | PLAN_CLASSES[5]
    | PLAN_CLASSES[6]
    | PLAN_CLASSES[7]
    | PLAN_CLASSES[8]
    | PLAN_CLASSES[9]
    | PLAN_CLASSES[10]
    | PLAN_CLASSES[11]
    | PLAN_CLASSES[12]
    | PLAN_CLASSES[13],
    Field(discriminator="component"),
]


class Chapter(StrictModel):
    chapter_id: str = Field(pattern=CHAPTER_ID)
    title: str = Field(min_length=1, max_length=80)
    tagline: str = Field(default="", max_length=160)
    first_scene: str = Field(pattern=SCENE_ID)
    last_scene: str = Field(pattern=SCENE_ID)
    hero_prompt: str = Field(min_length=10, max_length=300)
    # Index into the theme palette; the renderer wraps it.
    accent: int = Field(default=0, ge=0, le=11)


class Storyboard(StrictModel):
    scenes: list[Scene] = Field(min_length=1, max_length=120)
    # Empty for storyboards planned before chapters existed.
    chapters: list[Chapter] = Field(default_factory=list, max_length=MAX_CHAPTERS)

    @model_validator(mode="after")
    def chapters_cover_scenes(self):
        if not self.chapters:
            return self
        ids = [scene.scene_id for scene in self.scenes]
        cursor = 0
        for chapter in self.chapters:
            if cursor >= len(ids) or chapter.first_scene != ids[cursor]:
                raise ValueError(
                    f"{chapter.chapter_id} must start at scene {ids[cursor] if cursor < len(ids) else 'end'}"
                )
            if chapter.last_scene not in ids[cursor:]:
                raise ValueError(f"{chapter.chapter_id} ends before it starts")
            cursor = ids.index(chapter.last_scene) + 1
        if cursor != len(ids):
            raise ValueError("chapters must cover every scene")
        return self


class ChapterSpan(StrictModel):
    """Model-planned chapter over sentence numbers; the provider snaps spans."""

    first_sentence: int = Field(ge=1)
    last_sentence: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=80)
    tagline: str = Field(default="", max_length=160)
    hero_prompt: str = Field(min_length=10, max_length=300)


class ChapterPlan(StrictModel):
    chapters: list[ChapterSpan] = Field(min_length=1, max_length=MAX_CHAPTERS)


MAX_SCENE_SENTENCES = 6


class StoryboardChunk(StrictModel):
    """Model output for one slice of the script. The provider copies narration
    text and assigns scene ids, so the model never re-emits the script."""

    scenes: list[PlannedScene] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def spans(self):
        # Only per-scene bounds are enforced here. Small gaps or overlaps
        # between scenes are a common model slip; the provider snaps the
        # ranges to contiguous coverage of the chunk instead of failing.
        for scene in self.scenes:
            span = scene.last_sentence - scene.first_sentence + 1
            if not 1 <= span <= MAX_SCENE_SENTENCES:
                raise ValueError(
                    f"each scene must cover 1-{MAX_SCENE_SENTENCES} sentences "
                    f"(got {scene.first_sentence}-{scene.last_sentence})"
                )
        return self


class Metadata(StrictModel):
    title: str = Field(min_length=1, max_length=100)
    description: Prose = Field(max_length=5000)
    tags: list[Annotated[str, Field(max_length=100)]] = Field(max_length=20)
