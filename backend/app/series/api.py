"""HTTP routes for series, bibles, themes, and the idea backlog."""

from collections.abc import Callable
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..schemas import Source
from .library import BRAND_KINDS, AssetKind, SeriesLibrary, UnsupportedMedia
from .schema import SeriesBible, ThemeGuidance
from .store import SeriesConflict, SeriesNotFound, SeriesStore


def _not_blank(value):
    if value is not None and not value.strip():
        raise ValueError("must not be blank")
    return value.strip() if value is not None else value


class SeriesInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=160)
    slug: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9-]{0,79}$")
    description: str = Field(default="", max_length=5000)

    _name = field_validator("name")(_not_blank)


class SeriesPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=160)
    slug: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9-]{0,79}$")
    description: str | None = Field(default=None, max_length=5000)

    _name = field_validator("name")(_not_blank)


class ThemeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    blurb: str = Field(default="", max_length=1000)
    guidance: ThemeGuidance = Field(default_factory=ThemeGuidance)

    _name = field_validator("name")(_not_blank)


class ThemePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=120)
    blurb: str | None = Field(default=None, max_length=1000)
    guidance: ThemeGuidance | None = None

    _name = field_validator("name")(_not_blank)


class IdeaInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=160)
    pitch: str = Field(default="", max_length=3000)
    notes: str = Field(default="", max_length=1900)
    theme_id: str | None = None

    _title = field_validator("title")(_not_blank)


class IdeaPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, min_length=1, max_length=160)
    pitch: str | None = Field(default=None, max_length=3000)
    notes: str | None = Field(default=None, max_length=1900)
    theme_id: str | None = None
    status: Literal["backlog", "dropped"] | None = None

    _title = field_validator("title")(_not_blank)


class AssetPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=200)
    kind: AssetKind | None = None
    status: Literal["active", "archived"] | None = None


def idea_brief(idea) -> str:
    return "\n\n".join(part for part in (idea["pitch"], idea["notes"]) if part)


def series_router(
    series: SeriesStore,
    library: SeriesLibrary,
    jobs: Callable[[], list[dict]],
    start_job: Callable[[dict, BaseModel], dict],
    start_input: type[BaseModel],
    max_asset_bytes: int,
) -> APIRouter:
    """`start_job(idea, body)` creates the job; `start_input` validates its body."""
    router = APIRouter(prefix="/api/series")

    def guard(operation, *args, **kwargs):
        try:
            return operation(*args, **kwargs)
        except SeriesNotFound as exc:
            raise HTTPException(404, exc.args[0]) from exc
        except SeriesConflict as exc:
            raise HTTPException(409, str(exc)) from exc

    def referenced(key, value):
        return [job["id"] for job in jobs() if job.get(key) == value]

    def fields(body):
        return body.model_dump(exclude_unset=True)

    @router.get("")
    async def list_series():
        return series.list()

    @router.post("", status_code=201)
    async def create_series(body: SeriesInput):
        return guard(series.create, body.name, body.description, body.slug)

    @router.get("/{series_id}")
    async def get_series(series_id: str):
        return guard(series.get, series_id)

    @router.patch("/{series_id}")
    async def update_series(series_id: str, body: SeriesPatch):
        values = {
            key: value for key, value in fields(body).items() if value is not None
        }
        return guard(series.update, series_id, **values)

    @router.delete("/{series_id}", status_code=204)
    async def delete_series(series_id: str):
        guard(series.get, series_id)
        if referenced("series_id", series_id):
            raise HTTPException(
                409, "Series is used by existing videos; delete those videos first"
            )
        library.delete_series_media(series_id)
        guard(series.delete, series_id)
        return Response(status_code=204)

    @router.get("/{series_id}/jobs")
    async def series_jobs(series_id: str):
        guard(series.get, series_id)
        return [job for job in jobs() if job.get("series_id") == series_id]

    @router.get("/{series_id}/bible")
    async def get_bible(series_id: str):
        return guard(series.bible, series_id)

    @router.put("/{series_id}/bible")
    async def put_bible(series_id: str, body: SeriesBible):
        for field, kinds in BRAND_KINDS.items():
            asset_id = getattr(body.visual, field)
            if asset_id is None:
                continue
            try:
                asset = library.asset(series_id, asset_id)
            except SeriesNotFound:
                asset = None
            if not asset or asset["status"] != "active" or asset["kind"] not in kinds:
                raise HTTPException(
                    422,
                    f"visual.{field} must name an active {' or '.join(kinds)} asset "
                    "in this series' library",
                )
        return guard(series.put_bible, series_id, body)

    @router.get("/{series_id}/bible/versions")
    async def bible_versions(series_id: str):
        return guard(series.bible_versions, series_id)

    @router.get("/{series_id}/themes")
    async def list_themes(series_id: str):
        return guard(series.themes, series_id)

    @router.post("/{series_id}/themes", status_code=201)
    async def create_theme(series_id: str, body: ThemeInput):
        return guard(
            series.create_theme, series_id, body.name, body.blurb, body.guidance
        )

    @router.patch("/{series_id}/themes/{theme_id}")
    async def update_theme(series_id: str, theme_id: str, body: ThemePatch):
        values = {
            key: getattr(body, key)
            for key, value in fields(body).items()
            if value is not None
        }
        return guard(series.update_theme, series_id, theme_id, **values)

    @router.delete("/{series_id}/themes/{theme_id}", status_code=204)
    async def delete_theme(series_id: str, theme_id: str):
        guard(series.theme, series_id, theme_id)
        if referenced("theme_id", theme_id):
            raise HTTPException(
                409, "Theme is used by existing videos; delete those videos first"
            )
        guard(series.delete_theme, series_id, theme_id)
        return Response(status_code=204)

    @router.get("/{series_id}/ideas")
    async def list_ideas(series_id: str):
        statuses = {job["id"]: job["status"] for job in jobs()}
        return [
            {**idea, "job_status": statuses.get(idea["job_id"])}
            for idea in guard(series.ideas, series_id)
        ]

    @router.post("/{series_id}/ideas", status_code=201)
    async def create_idea(series_id: str, body: IdeaInput):
        return guard(
            series.create_idea,
            series_id,
            body.title,
            body.pitch,
            body.notes,
            body.theme_id,
        )

    @router.patch("/{series_id}/ideas/{idea_id}")
    async def update_idea(series_id: str, idea_id: str, body: IdeaPatch):
        values = fields(body)
        for key in ("title", "pitch", "notes", "status"):
            if values.get(key, "") is None:
                values.pop(key)
        return guard(series.update_idea, series_id, idea_id, **values)

    @router.delete("/{series_id}/ideas/{idea_id}", status_code=204)
    async def delete_idea(series_id: str, idea_id: str):
        guard(series.delete_idea, series_id, idea_id)
        return Response(status_code=204)

    @router.post("/{series_id}/ideas/{idea_id}/start", status_code=201)
    async def start_idea(series_id: str, idea_id: str, body: start_input):
        idea = guard(series.idea, series_id, idea_id)
        if idea["job_id"] or idea["status"] != "backlog":
            raise HTTPException(
                409, "Only backlog ideas without a video can be started"
            )
        return start_job(idea, body)

    @router.get("/{series_id}/assets")
    async def list_assets(series_id: str, include_archived: bool = False):
        return guard(library.assets, series_id, include_archived)

    @router.post("/{series_id}/assets", status_code=201)
    async def upload_asset(
        series_id: str,
        request: Request,
        name: str = Query(min_length=1, max_length=200),
        kind: AssetKind = "image",
    ):
        """Raw request body is the file; Content-Type declares its media type."""
        too_large = HTTPException(413, f"Assets are limited to {max_asset_bytes} bytes")
        declared = request.headers.get("content-length", "")
        if declared.isdigit() and int(declared) > max_asset_bytes:
            raise too_large
        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data) > max_asset_bytes:
                raise too_large
        try:
            result = await library.add(
                series_id,
                bytes(data),
                request.headers.get("content-type", ""),
                name.strip() or "Untitled",
                kind,
                {"origin": "upload"},
            )
        except SeriesNotFound as exc:
            raise HTTPException(404, exc.args[0]) from exc
        except UnsupportedMedia as exc:
            raise HTTPException(415, str(exc)) from exc
        return JSONResponse(result, status_code=200 if result["duplicate"] else 201)

    @router.patch("/{series_id}/assets/{asset_id}")
    async def update_asset(series_id: str, asset_id: str, body: AssetPatch):
        values = {
            key: value for key, value in fields(body).items() if value is not None
        }
        return guard(library.update, series_id, asset_id, **values)

    @router.get("/{series_id}/assets/{asset_id}/content")
    async def asset_content(series_id: str, asset_id: str):
        try:
            data, content_type, _, filename = await library.content(series_id, asset_id)
        except (SeriesNotFound, FileNotFoundError) as exc:
            raise HTTPException(404, "Asset not found") from exc
        return Response(
            data,
            media_type=content_type,
            headers={
                # Filename is the content hash, never the user-supplied name.
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-Content-Type-Options": "nosniff",
            },
        )

    @router.get("/{series_id}/sources")
    async def list_sources(series_id: str):
        return guard(library.sources, series_id)

    @router.post("/{series_id}/sources", status_code=201)
    async def add_source(series_id: str, body: Source):
        return guard(library.add_source, series_id, body.model_dump(mode="json"))

    @router.delete("/{series_id}/sources/{source_id}", status_code=204)
    async def delete_source(series_id: str, source_id: str):
        guard(library.delete_source, series_id, source_id)
        return Response(status_code=204)

    return router
