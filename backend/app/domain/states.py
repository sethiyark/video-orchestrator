"""Explicit resumable video states. Illegal transitions fail closed."""

from enum import StrEnum


class IllegalStateTransition(ValueError):
    def __init__(self, source: "VideoState", target: "VideoState"):
        super().__init__(f"Cannot transition from {source} to {target}")
        self.source = source
        self.target = target


class VideoState(StrEnum):
    DISCOVERED = "DISCOVERED"
    SCORED = "SCORED"
    SELECTED = "SELECTED"
    RESEARCHING = "RESEARCHING"
    RESEARCH_VERIFICATION = "RESEARCH_VERIFICATION"
    RESEARCH_APPROVED = "RESEARCH_APPROVED"
    OUTLINING = "OUTLINING"
    SCRIPTING = "SCRIPTING"
    SCRIPT_REVIEW = "SCRIPT_REVIEW"
    SCRIPT_APPROVED = "SCRIPT_APPROVED"
    STORYBOARDING = "STORYBOARDING"
    STORYBOARD_APPROVED = "STORYBOARD_APPROVED"
    ASSET_GENERATION = "ASSET_GENERATION"
    VOICE_GENERATION = "VOICE_GENERATION"
    ALIGNMENT = "ALIGNMENT"
    RENDERING = "RENDERING"
    VIDEO_QC = "VIDEO_QC"
    PACKAGING = "PACKAGING"
    PACKAGING_QC = "PACKAGING_QC"
    POLICY_QC = "POLICY_QC"
    READY_TO_UPLOAD = "READY_TO_UPLOAD"
    UPLOADED_PRIVATE = "UPLOADED_PRIVATE"
    SCHEDULED = "SCHEDULED"
    PUBLISHED = "PUBLISHED"
    OBSERVING = "OBSERVING"
    ANALYZED = "ANALYZED"
    LEARNED = "LEARNED"
    RESEARCH_FAILED = "RESEARCH_FAILED"
    SCRIPT_FAILED = "SCRIPT_FAILED"
    STORYBOARD_FAILED = "STORYBOARD_FAILED"
    ASSET_FAILED = "ASSET_FAILED"
    VOICE_FAILED = "VOICE_FAILED"
    RENDER_FAILED = "RENDER_FAILED"
    QC_FAILED = "QC_FAILED"
    POLICY_RISK = "POLICY_RISK"
    COPYRIGHT_RISK = "COPYRIGHT_RISK"
    COST_LIMIT_REACHED = "COST_LIMIT_REACHED"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"


_H = VideoState.HUMAN_REVIEW_REQUIRED
_C = VideoState.COST_LIMIT_REACHED

TRANSITIONS: dict[VideoState, frozenset[VideoState]] = {
    VideoState.DISCOVERED: frozenset({VideoState.SCORED, _H}),
    VideoState.SCORED: frozenset({VideoState.SELECTED, VideoState.DISCOVERED, _H}),
    VideoState.SELECTED: frozenset({VideoState.RESEARCHING, _C, _H}),
    VideoState.RESEARCHING: frozenset(
        {VideoState.RESEARCH_VERIFICATION, VideoState.RESEARCH_FAILED, _C, _H}
    ),
    VideoState.RESEARCH_VERIFICATION: frozenset(
        {VideoState.RESEARCH_APPROVED, VideoState.RESEARCH_FAILED, _H}
    ),
    VideoState.RESEARCH_APPROVED: frozenset({VideoState.OUTLINING, _H}),
    VideoState.OUTLINING: frozenset({VideoState.SCRIPTING, _H}),
    VideoState.SCRIPTING: frozenset(
        {VideoState.SCRIPT_REVIEW, VideoState.SCRIPT_FAILED, _C, _H}
    ),
    VideoState.SCRIPT_REVIEW: frozenset(
        {VideoState.SCRIPT_APPROVED, VideoState.SCRIPTING, VideoState.SCRIPT_FAILED, _H}
    ),
    VideoState.SCRIPT_APPROVED: frozenset({VideoState.STORYBOARDING, _H}),
    VideoState.STORYBOARDING: frozenset(
        {VideoState.STORYBOARD_APPROVED, VideoState.STORYBOARD_FAILED, _H}
    ),
    VideoState.STORYBOARD_APPROVED: frozenset({VideoState.ASSET_GENERATION, _H}),
    VideoState.ASSET_GENERATION: frozenset(
        {VideoState.VOICE_GENERATION, VideoState.ASSET_FAILED, _C, _H}
    ),
    VideoState.VOICE_GENERATION: frozenset(
        {VideoState.ALIGNMENT, VideoState.VOICE_FAILED, _H}
    ),
    VideoState.ALIGNMENT: frozenset(
        {VideoState.RENDERING, VideoState.VOICE_FAILED, _H}
    ),
    VideoState.RENDERING: frozenset(
        {VideoState.VIDEO_QC, VideoState.RENDER_FAILED, _H}
    ),
    VideoState.VIDEO_QC: frozenset(
        {VideoState.PACKAGING, VideoState.QC_FAILED, VideoState.RENDER_FAILED, _H}
    ),
    VideoState.PACKAGING: frozenset({VideoState.PACKAGING_QC, _H}),
    VideoState.PACKAGING_QC: frozenset(
        {VideoState.POLICY_QC, VideoState.QC_FAILED, _H}
    ),
    VideoState.POLICY_QC: frozenset(
        {
            VideoState.READY_TO_UPLOAD,
            VideoState.POLICY_RISK,
            VideoState.COPYRIGHT_RISK,
            _H,
        }
    ),
    VideoState.READY_TO_UPLOAD: frozenset({VideoState.UPLOADED_PRIVATE, _C, _H}),
    VideoState.UPLOADED_PRIVATE: frozenset(
        {VideoState.SCHEDULED, VideoState.PUBLISHED, _H}
    ),
    VideoState.SCHEDULED: frozenset({VideoState.PUBLISHED, _H}),
    VideoState.PUBLISHED: frozenset({VideoState.OBSERVING, _H}),
    VideoState.OBSERVING: frozenset({VideoState.ANALYZED, _H}),
    VideoState.ANALYZED: frozenset({VideoState.LEARNED, _H}),
    VideoState.LEARNED: frozenset({VideoState.LEARNED}),
    VideoState.RESEARCH_FAILED: frozenset(
        {VideoState.RESEARCHING, VideoState.SELECTED, _H}
    ),
    VideoState.SCRIPT_FAILED: frozenset(
        {VideoState.SCRIPTING, VideoState.SELECTED, _H}
    ),
    VideoState.STORYBOARD_FAILED: frozenset(
        {VideoState.STORYBOARDING, VideoState.SCRIPT_APPROVED, _H}
    ),
    VideoState.ASSET_FAILED: frozenset({VideoState.ASSET_GENERATION, _H}),
    VideoState.VOICE_FAILED: frozenset({VideoState.VOICE_GENERATION, _H}),
    VideoState.RENDER_FAILED: frozenset({VideoState.RENDERING, _H}),
    VideoState.QC_FAILED: frozenset(
        {VideoState.RENDERING, VideoState.PACKAGING, VideoState.VIDEO_QC, _H}
    ),
    VideoState.POLICY_RISK: frozenset({VideoState.PACKAGING, _H}),
    VideoState.COPYRIGHT_RISK: frozenset({_H}),
    VideoState.COST_LIMIT_REACHED: frozenset({_H, VideoState.SELECTED}),
    VideoState.HUMAN_REVIEW_REQUIRED: frozenset(
        {
            VideoState.SELECTED,
            VideoState.RESEARCHING,
            VideoState.SCRIPTING,
            VideoState.STORYBOARDING,
            VideoState.ASSET_GENERATION,
            VideoState.RENDERING,
            VideoState.READY_TO_UPLOAD,
            VideoState.UPLOADED_PRIVATE,
        }
    ),
}


def can_transition(source: VideoState, target: VideoState) -> bool:
    return target in TRANSITIONS[source]


def transition(source: VideoState, target: VideoState) -> VideoState:
    if not can_transition(source, target):
        raise IllegalStateTransition(source, target)
    return target
