import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect

from app.artifacts import Artifacts
from app.config import Settings
from app.local_provider import LocalProvider, ReviewRequired
from app.main import create_app
from app.providers import MockProvider
from app.series import SeriesBible, SeriesStore
from app.series.library import SeriesLibrary
from app.storage import LocalObjectStore
from app.store import Store

SOURCE = {
    "id": "s1",
    "url": "https://example.com",
    "title": "Reference",
    "excerpt": "DNS maps domain names to IP addresses.",
}
# Pydantic's HttpUrl normalises the URL, as it does for inline job sources.
STORED_SOURCE = {**SOURCE, "url": "https://example.com/"}
BIBLE = {
    "voice": {"tone": "dry", "style_rules": ["Short sentences"]},
    "visual": {"palette": ["#112233"], "image_style": "flat vector"},
    "glossary": [{"term": "Resolver", "definition": "Answers DNS queries"}],
}


def client(tmp_path):
    return TestClient(create_app(str(tmp_path / "jobs.db"), MockProvider(0)))


def make_series(api, **bible):
    series = api.post("/api/series", json={"name": "Systems Deep Dives"}).json()
    api.put(f"/api/series/{series['id']}/bible", json=bible or BIBLE)
    return series


def test_migration_creates_series_tables(tmp_path):
    store = Store(str(tmp_path / "jobs.db"))
    tables = set(inspect(store.engine).get_table_names())
    assert {"series", "series_bibles", "series_themes", "series_ideas"} <= tables


def test_series_crud_and_append_only_bible(tmp_path):
    with client(tmp_path) as api:
        assert api.post("/api/series", json={"name": "  "}).status_code == 422
        series = make_series(api)
        sid = series["id"]
        assert series["slug"] == "systems-deep-dives"
        assert (
            api.post("/api/series", json={"name": "Systems deep dives"}).status_code
            == 409
        )
        assert api.get("/api/series").json()[0]["id"] == sid

        bad = {"visual": {"palette": ["red"]}}
        assert api.put(f"/api/series/{sid}/bible", json=bad).status_code == 422
        assert api.put(f"/api/series/{sid}/bible", json={"extra": 1}).status_code == 422
        second = api.put(f"/api/series/{sid}/bible", json={"voice": {"tone": "warm"}})
        assert second.json()["version"] == 2
        versions = api.get(f"/api/series/{sid}/bible/versions").json()
        assert [item["version"] for item in versions] == [2, 1]
        assert (
            api.get(f"/api/series/{sid}/bible").json()["document"]["voice"]["tone"]
            == "warm"
        )

        patched = api.patch(f"/api/series/{sid}", json={"description": "Deep"}).json()
        assert patched["description"] == "Deep"
        assert api.get("/api/series/missing").status_code == 404
        assert api.delete(f"/api/series/{sid}").status_code == 204
        assert api.get(f"/api/series/{sid}").status_code == 404


def test_theme_must_belong_to_series_and_merges_guidance(tmp_path):
    with client(tmp_path) as api:
        sid = make_series(api)["id"]
        other = api.post("/api/series", json={"name": "Other"}).json()["id"]
        theme = api.post(
            f"/api/series/{sid}/themes",
            json={
                "name": "Databases",
                "blurb": "Storage engines",
                "guidance": {
                    "voice": {"style_rules": ["Use a running bank example"]},
                    "glossary": [{"term": "WAL", "definition": "Write-ahead log"}],
                },
            },
        ).json()
        assert (
            api.patch(
                f"/api/series/{other}/themes/{theme['id']}", json={"name": "x"}
            ).status_code
            == 404
        )
        assert (
            api.post(
                "/api/jobs",
                json={"title": "T", "series_id": other, "theme_id": theme["id"]},
            ).status_code
            == 422
        )
        assert (
            api.post(
                "/api/jobs", json={"title": "T", "theme_id": theme["id"]}
            ).status_code
            == 422
        )

        job = api.post(
            "/api/jobs",
            json={"title": "B-trees", "series_id": sid, "theme_id": theme["id"]},
        ).json()
        guidance = job["series_context"]["guidance"]
        assert guidance["voice"]["style_rules"] == [
            "Short sentences",
            "Use a running bank example",
        ]
        assert [entry["term"] for entry in guidance["glossary"]] == ["Resolver", "WAL"]
        assert job["series_context"]["theme"]["blurb"] == "Storage engines"
        assert job["series_id"] == sid and job["series_stale"] is False

        # Referenced themes and series cannot be deleted out from under a job.
        assert api.delete(f"/api/series/{sid}/themes/{theme['id']}").status_code == 409
        assert api.delete(f"/api/series/{sid}").status_code == 409


def test_bible_change_marks_job_stale_until_restart(tmp_path):
    with client(tmp_path) as api:
        sid = make_series(api)["id"]
        standalone = api.post("/api/jobs", json={"title": "Plain"}).json()
        assert standalone["series_id"] is None and standalone["series_stale"] is False
        job = api.post("/api/jobs", json={"title": "DNS", "series_id": sid}).json()
        snapshot = job["series_context"]

        # Re-saving identical content bumps the version but does not stale the job.
        api.put(f"/api/series/{sid}/bible", json=BIBLE)
        assert api.get(f"/api/jobs/{job['id']}").json()["series_stale"] is False

        api.put(f"/api/series/{sid}/bible", json={**BIBLE, "voice": {"tone": "warm"}})
        stale = api.get(f"/api/jobs/{job['id']}").json()
        assert stale["series_stale"] is True
        assert stale["series_context"] == snapshot
        response = api.post(f"/api/jobs/{job['id']}/run")
        assert response.status_code == 409
        assert "series bible" in response.json()["detail"]
        assert api.get(f"/api/series/{sid}/jobs").json()[0]["series_stale"] is True

        restarted = api.post(f"/api/jobs/{job['id']}/restart").json()
        assert restarted["series_stale"] is False
        assert restarted["series_context"]["guidance"]["voice"]["tone"] == "warm"
        assert restarted["series_context"]["bible_version"] == 3


def test_idea_start_links_job_and_delete_releases_it(tmp_path):
    with client(tmp_path) as api:
        sid = make_series(api)["id"]
        idea = api.post(
            f"/api/series/{sid}/ideas",
            json={
                "title": "How DNS caches",
                "pitch": "TTL walkthrough",
                "notes": "Use dig",
            },
        ).json()
        assert idea["status"] == "backlog"
        assert (
            api.post(
                f"/api/series/{sid}/ideas", json={"title": "x", "theme_id": "missing"}
            ).status_code
            == 404
        )

        job = api.post(f"/api/series/{sid}/ideas/{idea['id']}/start", json={}).json()
        assert job["title"] == "How DNS caches"
        assert job["brief"] == "TTL walkthrough\n\nUse dig"
        assert job["idea_id"] == idea["id"] and job["series_id"] == sid
        listed = api.get(f"/api/series/{sid}/ideas").json()[0]
        assert listed["status"] == "started" and listed["job_id"] == job["id"]
        assert listed["job_status"] == "draft"
        assert (
            api.post(f"/api/series/{sid}/ideas/{idea['id']}/start", json={}).status_code
            == 409
        )
        assert (
            api.patch(
                f"/api/series/{sid}/ideas/{idea['id']}", json={"status": "dropped"}
            ).status_code
            == 409
        )

        assert api.delete(f"/api/jobs/{job['id']}").status_code == 204
        released = api.get(f"/api/series/{sid}/ideas").json()[0]
        assert released["status"] == "backlog" and released["job_id"] is None
        dropped = api.patch(
            f"/api/series/{sid}/ideas/{idea['id']}", json={"status": "dropped"}
        )
        assert dropped.json()["status"] == "dropped"


class RecordingRunner:
    def __init__(self, outputs):
        self.outputs = iter(outputs)
        self.calls = []

    async def run(self, role, payload, job_id):
        self.calls.append(payload)
        provenance = {"repo_id": role, "revision": "fixture"}
        if "requests" not in payload:
            return {**next(self.outputs), "provenance": provenance}
        return {
            "results": [{"result": next(self.outputs)} for _ in payload["requests"]],
            "provenance": provenance,
        }


def local_series_job(tmp_path, outputs):
    settings = Settings()
    settings.artifact_dir = tmp_path / "artifacts"
    store = Store(str(tmp_path / "jobs.db"))
    series = SeriesStore(store.engine)
    sid = series.create("Networking")["id"]
    series.put_bible(sid, SeriesBible.model_validate(BIBLE))
    runner = RecordingRunner(outputs)
    provider = LocalProvider(settings, store, runner)
    job = store.create("DNS", "", [SOURCE], "local", None, series.resolve_context(sid))
    return provider, runner, job


def complete(job, name, output):
    stage = next(s for s in job["stages"] if s["name"] == name)
    stage["output"], stage["status"] = output, "completed"


def messages(payload):
    request = payload["requests"][0]
    return request["messages"][0]["content"], json.loads(
        request["messages"][1]["content"]
    )


def test_local_prompts_receive_stage_specific_series_guidance(tmp_path):
    verified = [
        {
            "id": "c1",
            "text": "DNS maps names",
            "source_id": "s1",
            "quote": SOURCE["excerpt"],
        }
    ]
    section = {
        "title": "DNS",
        "purpose": "Explain",
        "claim_ids": ["c1"],
        "estimated_seconds": 10,
    }
    script = {
        "text": "DNS maps names to addresses for every lookup you make.",
        "claim_ids": ["c1"],
    }
    critic = {"score": 9, "issues": [], "required_changes": [], "optional_changes": []}
    scene = {
        "first_sentence": 1,
        "last_sentence": 1,
        "component": "DefinitionCard",
        "props": {"title": "DNS", "body": "Names to addresses"},
    }
    provider, runner, job = local_series_job(
        tmp_path,
        [{"sections": [section]}, script, *[critic] * 5, {"scenes": [scene]}],
    )
    complete(job, "verification", {"verified_claims": verified})

    async def scenario():
        for stage in ["outline", "script", "critique", "storyboard"]:
            complete(job, stage, await provider.execute(stage, job))

    asyncio.run(scenario())
    outline, script_call, critique, storyboard = runner.calls
    system, data = messages(outline)
    assert "never evidence" in system
    assert set(data["series"]) == {"voice", "glossary"}
    assert messages(script_call)[1]["series"]["voice"]["tone"] == "dry"
    styles = [request["messages"][0]["content"] for request in critique["requests"]]
    assert sum("Enforce the series voice" in content for content in styles) == 1
    assert all(
        "series" in json.loads(r["messages"][1]["content"])
        for r in critique["requests"]
    )
    assert set(messages(storyboard)[1]["series"]) == {"visual"}


def test_standalone_local_prompts_are_unchanged(tmp_path):
    provider, runner, job = local_series_job(
        tmp_path,
        [
            {
                "sections": [
                    {
                        "title": "DNS",
                        "purpose": "Explain",
                        "claim_ids": ["c1"],
                        "estimated_seconds": 30,
                    }
                ]
            }
        ],
    )
    job["series_context"] = None
    complete(job, "verification", {"verified_claims": [{"id": "c1", "text": "DNS"}]})
    asyncio.run(provider.execute("outline", job))
    system, data = messages(runner.calls[0])
    assert "series" not in data and "never evidence" not in system


def test_glossary_cannot_stand_in_for_evidence(tmp_path):
    provider, _, job = local_series_job(
        tmp_path,
        [
            {
                "summary": "DNS",
                "claims": [
                    {
                        "id": "c1",
                        "text": "A resolver answers DNS queries",
                        "source_id": "s1",
                        "quote": "Answers DNS queries",
                    }
                ],
            }
        ],
    )
    with pytest.raises(ReviewRequired, match="unsupported"):
        asyncio.run(provider.execute("research", job))


PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
WAV = b"RIFF\x24\x00\x00\x00WAVEfmt " + b"\x00" * 24


def library_client(tmp_path, max_bytes=None):
    settings = Settings()
    settings.artifact_dir = tmp_path / "artifacts"
    if max_bytes:
        settings.series_asset_max_bytes = max_bytes
    app = create_app(str(tmp_path / "jobs.db"), MockProvider(0), settings)
    return TestClient(app), settings


def upload(api, sid, data, content_type, name="Logo", kind="logo"):
    return api.post(
        f"/api/series/{sid}/assets",
        params={"name": name, "kind": kind},
        content=data,
        headers={"Content-Type": content_type},
    )


def test_asset_upload_allowlist_dedupe_and_archive(tmp_path):
    api, settings = library_client(tmp_path, max_bytes=1024)
    with api:
        sid = make_series(api)["id"]
        first = upload(api, sid, PNG, "image/png")
        assert first.status_code == 201
        asset = first.json()
        assert asset["duplicate"] is False and asset["sha256"]
        stored = settings.artifact_dir / "series" / sid / f"{asset['sha256']}.png"
        assert stored.read_bytes() == PNG

        again = upload(api, sid, PNG, "image/png", name="Other")
        assert again.status_code == 200
        assert again.json()["id"] == asset["id"] and again.json()["duplicate"]

        svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
        assert upload(api, sid, svg, "image/svg+xml").status_code == 415
        # A declared type must match the bytes.
        assert upload(api, sid, b"<html>hi</html>", "image/png").status_code == 415
        assert upload(api, sid, PNG + b"\x00" * 2048, "image/png").status_code == 413
        assert upload(api, "missing", WAV, "audio/wav").status_code == 404

        content = api.get(f"/api/series/{sid}/assets/{asset['id']}/content")
        assert content.content == PNG
        assert content.headers["content-type"] == "image/png"
        assert content.headers["x-content-type-options"] == "nosniff"
        assert content.headers["content-disposition"].startswith("attachment")

        archived = api.patch(
            f"/api/series/{sid}/assets/{asset['id']}", json={"status": "archived"}
        )
        assert archived.json()["status"] == "archived"
        assert api.get(f"/api/series/{sid}/assets").json() == []
        listed = api.get(
            f"/api/series/{sid}/assets", params={"include_archived": True}
        ).json()
        assert [item["id"] for item in listed] == [asset["id"]]
        other = api.post("/api/series", json={"name": "Other"}).json()["id"]
        assert (
            api.get(f"/api/series/{other}/assets/{asset['id']}/content").status_code
            == 404
        )


def test_library_sources_are_copied_into_jobs(tmp_path):
    api, _ = library_client(tmp_path)
    with api:
        sid = make_series(api)["id"]
        source = api.post(f"/api/series/{sid}/sources", json=SOURCE).json()
        assert api.post(f"/api/series/{sid}/sources", json=SOURCE).status_code == 409
        assert (
            api.post(
                f"/api/series/{sid}/sources",
                json={**SOURCE, "id": "s2", "excerpt": "short"},
            ).status_code
            == 422
        )

        job = api.post(
            "/api/jobs",
            json={
                "title": "DNS",
                "series_id": sid,
                "library_source_ids": [source["id"]],
            },
        ).json()
        assert job["sources"] == [STORED_SOURCE]
        # Deleting the library entry does not touch the job's snapshot.
        assert (
            api.delete(f"/api/series/{sid}/sources/{source['id']}").status_code == 204
        )
        assert api.get(f"/api/jobs/{job['id']}").json()["sources"] == [STORED_SOURCE]

        again = api.post(f"/api/series/{sid}/sources", json=SOURCE).json()
        duplicate = api.post(
            "/api/jobs",
            json={
                "title": "DNS",
                "series_id": sid,
                "sources": [SOURCE],
                "library_source_ids": [again["id"]],
            },
        )
        assert duplicate.status_code == 422
        standalone = api.post(
            "/api/jobs", json={"title": "DNS", "library_source_ids": [again["id"]]}
        )
        assert standalone.status_code == 422
        missing = api.post(
            "/api/jobs",
            json={"title": "DNS", "series_id": sid, "library_source_ids": ["nope"]},
        )
        assert missing.status_code == 422

        idea = api.post(f"/api/series/{sid}/ideas", json={"title": "Caching"}).json()
        started = api.post(
            f"/api/series/{sid}/ideas/{idea['id']}/start",
            json={"library_source_ids": [again["id"]]},
        ).json()
        assert started["sources"] == [STORED_SOURCE]


def test_library_source_counts_for_local_mode_and_quotes_still_checked(tmp_path):
    settings = Settings()
    settings.mode = "local"
    settings.artifact_dir = tmp_path / "artifacts"
    store = Store(str(tmp_path / "jobs.db"))
    provider = LocalProvider(settings, store, RecordingRunner([]))
    with TestClient(create_app(str(tmp_path / "jobs.db"), provider, settings)) as api:
        sid = make_series(api)["id"]
        assert (
            api.post("/api/jobs", json={"title": "DNS", "series_id": sid}).status_code
            == 422
        )
        source = api.post(f"/api/series/{sid}/sources", json=SOURCE).json()
        job = api.post(
            "/api/jobs",
            json={
                "title": "DNS",
                "series_id": sid,
                "library_source_ids": [source["id"]],
            },
        )
        assert job.status_code == 201
    provider, _, job = local_series_job(
        tmp_path / "quotes",
        [
            {
                "summary": "DNS",
                "claims": [
                    {
                        "id": "c1",
                        "text": "Invented",
                        "source_id": "s1",
                        "quote": "Library excerpts do not say this.",
                    }
                ],
            }
        ],
    )
    with pytest.raises(ReviewRequired, match="unsupported"):
        asyncio.run(provider.execute("research", job))


def test_promote_media_artifact_into_series_library(tmp_path):
    api, settings = library_client(tmp_path)
    with api:
        store = api.app.state.store
        sid = make_series(api)["id"]
        job = api.post("/api/jobs", json={"title": "DNS", "series_id": sid}).json()
        standalone = api.post("/api/jobs", json={"title": "Plain"}).json()
        artifacts = Artifacts(settings.artifact_dir)
        wav = tmp_path / "narration.wav"
        wav.write_bytes(WAV)
        audio = artifacts.adopt(job["id"], wav)
        stray = tmp_path / "stray.png"
        stray.write_bytes(PNG)
        unreferenced = artifacts.adopt(job["id"], stray)
        stage_json = artifacts.put_json(job["id"], {"x": 1})
        record = store.get(job["id"])
        narration = next(s for s in record["stages"] if s["name"] == "narration")
        narration["output"] = {"audio": audio, "provenance": {"repo_id": "tts"}}
        narration["status"] = "completed"
        store.save(record)

        url = f"/api/jobs/{job['id']}/artifacts/{{}}/promote"
        body = {"name": "Intro narration", "kind": "audio"}
        promoted = api.post(url.format(audio["id"]), json=body)
        assert promoted.status_code == 201
        asset = promoted.json()
        assert asset["provenance"] == {
            "origin": "promoted",
            "job_id": job["id"],
            "artifact_id": audio["id"],
            "stage": "narration",
            "model": {"repo_id": "tts"},
        }
        assert asset["sha256"] == audio["sha256"]
        assert api.get(f"/api/series/{sid}/assets/{asset['id']}/content").content == WAV
        assert api.post(url.format(audio["id"]), json=body).status_code == 200

        assert api.post(url.format(stage_json["id"]), json=body).status_code == 415
        assert api.post(url.format(unreferenced["id"]), json=body).status_code == 404
        assert api.post(url.format("missing.wav"), json=body).status_code == 404
        other = f"/api/jobs/{standalone['id']}/artifacts/{audio['id']}/promote"
        assert api.post(other, json=body).status_code == 409


def storyboard_scene(asset_id):
    return {
        "first_sentence": 1,
        "last_sentence": 1,
        "component": "SeriesAsset",
        "props": {"title": "Our logo", "asset_id": asset_id},
    }


def test_series_asset_scene_is_validated_and_pinned(tmp_path):
    script = {
        "text": "DNS maps names to addresses for every lookup you make.",
        "claim_ids": ["c1"],
    }
    provider, runner, job = local_series_job(tmp_path, [])
    library = SeriesLibrary(
        provider.store.engine, LocalObjectStore(tmp_path / "objects")
    )
    sid = job["series_id"]
    logo = asyncio.run(library.add(sid, PNG, "image/png", "Logo", "logo", {}))
    music = asyncio.run(library.add(sid, WAV, "audio/wav", "Sting", "music", {}))
    complete(job, "script", script)

    # A non-visual asset or an unknown id fails closed.
    for bad in (music["id"], "not-an-asset"):
        runner.outputs = iter([{"scenes": [storyboard_scene(bad)]}])
        with pytest.raises(ReviewRequired, match="series asset"):
            asyncio.run(provider.execute("storyboard", job))

    runner.outputs = iter([{"scenes": [storyboard_scene(logo["id"])]}])
    storyboard = asyncio.run(provider.execute("storyboard", job))
    system, data = messages(runner.calls[-1])
    assert "SeriesAsset may show" in system
    assert data["series_assets"] == [{"id": logo["id"], "name": "Logo", "kind": "logo"}]
    complete(job, "storyboard", storyboard)

    assets = asyncio.run(provider.execute("assets", job))
    assert assets["series_assets"] == [
        {
            "scene_id": "scene_001",
            "asset_id": logo["id"],
            "sha256": logo["sha256"],
            "name": "Logo",
        }
    ]
    library.update(sid, logo["id"], status="archived")
    with pytest.raises(ReviewRequired, match="not an active image or logo"):
        asyncio.run(provider.execute("assets", job))


def test_standalone_storyboard_forbids_series_assets(tmp_path):
    provider, runner, job = local_series_job(tmp_path, [])
    job["series_context"], job["series_id"] = None, None
    complete(
        job, "script", {"text": "DNS maps names to addresses.", "claim_ids": ["c1"]}
    )
    runner.outputs = iter([{"scenes": [storyboard_scene("anything")]}])
    with pytest.raises(ReviewRequired, match="series asset"):
        asyncio.run(provider.execute("storyboard", job))
    assert "Do not use SeriesAsset" in messages(runner.calls[0])[0]
