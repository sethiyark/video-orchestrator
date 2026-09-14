"""Series bible documents. Style data only: never evidence, never executable."""

from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from ..schemas import COMPONENTS, StrictModel

# Storyboard component names a bible may prefer; the same closed enum the
# storyboard schema accepts.
Component = Literal[COMPONENTS]
Hex = Annotated[str, StringConstraints(pattern=r"^#[0-9a-fA-F]{6}$")]
Rule = Annotated[str, StringConstraints(min_length=1, max_length=300)]


class VoiceGuide(StrictModel):
    audience: str = Field(default="", max_length=300)
    tone: str = Field(default="", max_length=300)
    style_rules: list[Rule] = Field(default_factory=list, max_length=20)
    avoid_phrases: list[Rule] = Field(default_factory=list, max_length=40)


AssetId = Annotated[str, StringConstraints(min_length=1, max_length=36)]


class VisualGuide(StrictModel):
    palette: list[Hex] = Field(default_factory=list, max_length=12)
    preferred_components: list[Component] = Field(default_factory=list, max_length=4)
    image_style: str = Field(default="", max_length=300)
    # Brand kit: ids of active series library assets the renderer reuses in
    # every video of the series (validated against the library on save).
    logo_asset_id: AssetId | None = None
    intro_asset_id: AssetId | None = None
    outro_asset_id: AssetId | None = None
    music_asset_id: AssetId | None = None


class GlossaryEntry(StrictModel):
    term: str = Field(min_length=1, max_length=80)
    definition: str = Field(min_length=1, max_length=500)


class SeriesBible(StrictModel):
    voice: VoiceGuide = Field(default_factory=VoiceGuide)
    visual: VisualGuide = Field(default_factory=VisualGuide)
    glossary: list[GlossaryEntry] = Field(default_factory=list, max_length=100)


class ThemeGuidance(SeriesBible):
    """Additive overlay: lists extend the base bible, non-empty scalars replace it."""


def merge(base: dict, overlay: dict) -> dict:
    merged = {}
    for key, value in base.items():
        extra = overlay.get(key)
        if isinstance(value, dict):
            merged[key] = merge(value, extra or {})
        elif isinstance(value, list):
            merged[key] = value + [item for item in extra or [] if item not in value]
        else:
            merged[key] = extra or value
    return merged
