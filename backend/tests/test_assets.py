"""Assets stage: one image per scene, heroes first, batched local generation
with a cross-job cache, or the manual Claude/Gemini relay."""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from test_local_api import PipelineFixtureRunner
from test_local_provider import complete, setup
from test_pipeline import wait

from app.config import Settings
from app.local_provider import (
    IMAGE_BATCH,
    LocalProvider,
    ManualStepRequired,
    ReviewRequired,
)
from app.main import create_app
from app.rendering import RenderError
from app.store import Store

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def board(scene_count, chapters=1):
    per = -(-scene_count // chapters)
    scenes = [
        {
            "scene_id": f"scene_{i:03d}",
            "narration_text": f"Sentence {i}.",
            "duration_seconds": 3,
            "image_prompt": f"Illustration {i}",
            "component": "Outro" if i == scene_count else "DefinitionCard",
            "props": {"title": "T", "takeaways": ["a"]}
            if i == scene_count
            else {"title": "T", "body": "B"},
        }
        for i in range(1, scene_count + 1)
    ]
    return {
        "scenes": scenes,
        "chapters": [
            {
                "chapter_id": f"chapter_{c + 1:02d}",
                "title": f"Chapter {c + 1}",
                "tagline": "",
                "first_scene": scenes[c * per]["scene_id"],
                "last_scene": scenes[min((c + 1) * per, scene_count) - 1]["scene_id"],
                "hero_prompt": f"Hero illustration {c + 1}",
                "accent": c,
            }
            for c in range(chapters)
        ],
    }


class ImageRunner:
    """Writes a PNG per prompt like the diffusion child; records batches."""

    def __init__(self):
        self.batches = []

    async def run(self, role, payload, job_id):
        assert role == "images" and "prompts" in payload
        self.batches.append(payload["prompts"])
        results = []
        for item in payload["prompts"]:
            Path(item["output_path"]).write_bytes(PNG + item["prompt"].encode())
            results.append({"width": 1024, "height": 576, **item})
        return {"results": results, "provenance": {"role": role, "revision": "fx"}}


def image_provider(tmp_path):
    provider, _, job = setup(tmp_path, [])
    runner = ImageRunner()
    provider.runner = runner
    provider.settings.models.images_enabled = True
    provider.settings.models.routes["assets"] = "images"
    return provider, runner, job


def test_images_are_batched_hero_first_and_cached_across_jobs(tmp_path):
    provider, runner, job = image_provider(tmp_path)
    try:
        complete(job, "storyboard", board(30, chapters=2))
        result = asyncio.run(provider.execute("assets", job))
        ids = [image["id"] for image in result["images"]]
        assert ids[:2] == ["chapter_01", "chapter_02"]
        assert ids[2:] == [f"scene_{i:03d}" for i in range(1, 31)]
        assert [len(batch) for batch in runner.batches] == [IMAGE_BATCH, 32 - IMAGE_BATCH]
        assert [p["seed"] for p in runner.batches[0]][:3] == [42, 43, 44]
        assert all(image["cache"] == "miss" for image in result["images"])
        first = result["images"][0]["artifact"]
        assert provider.artifacts.resolve(job["id"], first["id"]).read_bytes().startswith(PNG)

        # The same prompts in another job hit the cache: no model child at all,
        # and the image is copied into the new job's own artifact folder.
        other = provider.store.create("DNS again", "", job["sources"])
        complete(other, "storyboard", board(30, chapters=2))
        runner.batches.clear()
        again = asyncio.run(provider.execute("assets", other))
        assert runner.batches == []
        assert {image["cache"] for image in again["images"]} == {"hit"}
        copied = provider.artifacts.resolve(other["id"], again["images"][0]["artifact"]["id"])
        assert copied.read_bytes() == provider.artifacts.resolve(job["id"], first["id"]).read_bytes()
        assert copied.parent.name == other["id"]
    finally:
        provider.settings.models.images_enabled = False
        provider.settings.models.routes["assets"] = "manual"


def test_image_budget_keeps_heroes_and_marks_fallbacks(tmp_path):
    provider, _, job = image_provider(tmp_path)
    try:
        provider.settings.models.governor.max_images = 4
        complete(job, "storyboard", board(6, chapters=2))
        result = asyncio.run(provider.execute("assets", job))
        assert result["image_budget"] == 4
        generated = [i["id"] for i in result["images"] if "artifact" in i]
        assert generated == ["chapter_01", "chapter_02", "scene_001", "scene_002"]
        fallback = [i for i in result["images"] if i.get("fallback")]
        assert [i["id"] for i in fallback] == ["scene_003", "scene_004", "scene_005", "scene_006"]
        assert all(i["fallback"] == "chapter_hero" for i in fallback)

        provider.settings.models.governor.max_images = 1
        with pytest.raises(ReviewRequired, match="image budget"):
            asyncio.run(provider.execute("assets", job))
    finally:
        provider.settings.models.governor.max_images = 120
        provider.settings.models.images_enabled = False
        provider.settings.models.routes["assets"] = "manual"


def test_failed_prompt_in_batch_is_retryable(tmp_path):
    provider, _, job = image_provider(tmp_path)

    async def run(role, payload, job_id):
        return {"results": [{"error": "NaN latents"}] * len(payload["prompts"]), "provenance": {}}

    provider.runner.run = run
    try:
        complete(job, "storyboard", board(2))
        with pytest.raises(RuntimeError, match="NaN latents"):
            asyncio.run(provider.execute("assets", job))
    finally:
        provider.settings.models.images_enabled = False
        provider.settings.models.routes["assets"] = "manual"


def test_manual_relay_parks_with_prompts_and_resumes_from_uploads(tmp_path):
    provider, runner, job = setup(tmp_path, [])
    provider.settings.models.images_enabled = True
    try:
        assert provider.settings.models.routes["assets"] == "manual"
        complete(job, "storyboard", board(3))
        with pytest.raises(ManualStepRequired) as info:
            asyncio.run(provider.execute("assets", job))
        assert runner.calls == []
        assert info.value.schema_names == []
        expected = info.value.extra["expected_images"]
        assert [i["id"] for i in expected] == ["chapter_01", "scene_001", "scene_002", "scene_003"]
        assert info.value.extra["missing"] == [i["id"] for i in expected]
        assert "[chapter_01] (chapter hero)" in info.value.prompt
        assert "Prompt: Illustration 2" in info.value.prompt

        # Simulate what the upload endpoint stores, plus one skipped scene.
        with open(tmp_path / "hero.png", "wb") as handle:
            handle.write(PNG)
        artifact = provider.artifacts.adopt(job["id"], tmp_path / "hero.png")
        stage = next(s for s in job["stages"] if s["name"] == "assets")
        stage["output"] = {
            "manual": {
                "expected_images": expected,
                "images": {
                    "chapter_01": {"artifact": artifact},
                    "scene_001": {"artifact": artifact},
                    "scene_003": {"artifact": artifact},
                },
                "skipped": ["scene_002"],
            }
        }
        result = asyncio.run(provider.execute("assets", job))
        assert [(i["id"], i.get("cache"), i.get("fallback")) for i in result["images"]] == [
            ("chapter_01", "manual", None),
            ("scene_001", "manual", None),
            ("scene_002", None, "chapter_hero"),
            ("scene_003", "manual", None),
        ]
        assert result["images"][0]["provenance"] == {"manual": True}

        # A hero cannot be satisfied by a skip: the stage parks again for it.
        stage["output"]["manual"]["images"].pop("chapter_01")
        stage["output"]["manual"]["skipped"].append("chapter_01")
        with pytest.raises(ManualStepRequired) as info:
            asyncio.run(provider.execute("assets", job))
        assert info.value.extra["missing"] == ["chapter_01"]
        assert "1 of 4 still needed (3 uploaded)" in info.value.prompt
    finally:
        provider.settings.models.images_enabled = False


def test_manual_image_relay_via_api(tmp_path):
    settings = Settings()
    settings.mode = "local"
    settings.artifact_dir = tmp_path / "artifacts"
    settings.cache_dir = tmp_path / "models"
    settings.models.images_enabled = True
    path = str(tmp_path / "jobs.db")
    store = Store(path)
    provider = LocalProvider(settings, store, PipelineFixtureRunner())

    class TwoSceneRunner(PipelineFixtureRunner):
        async def run(self, role, payload, job_id):
            response = await super().run(role, payload, job_id)
            for request, item in zip(payload.get("requests", []), response.get("results", [])):
                if request["schema_name"] == "StoryboardChunk":
                    item["result"] = {
                        "scenes": [
                            {
                                "first_sentence": 1,
                                "last_sentence": 1,
                                "component": "Outro",
                                "props": {"title": "DNS", "takeaways": ["x"]},
                                "image_prompt": "A resolver answering a browser",
                            }
                        ]
                    }
            return response

    provider.runner = TwoSceneRunner()
    provider.renderer.render = AsyncMock(
        side_effect=RenderError("Remotion/FFmpeg unavailable in this offline fixture")
    )
    try:
        with TestClient(create_app(path, provider, settings)) as client:
            job_id = client.post(
                "/api/jobs",
                json={
                    "title": "DNS",
                    "sources": [
                        {
                            "id": "s1",
                            "url": "https://example.com",
                            "title": "DNS reference",
                            "excerpt": "DNS maps domain names to IP addresses.",
                        }
                    ],
                },
            ).json()["id"]
            assert client.post(f"/api/jobs/{job_id}/run").status_code == 200
            job = wait(client, job_id, "awaiting_manual_input")
            stage = next(s for s in job["stages"] if s["name"] == "assets")
            manual = stage["output"]["manual"]
            assert manual["missing"] == ["chapter_01", "scene_001"]
            assert "Prompt: A resolver answering a browser" in manual["prompt"]
            base = f"/api/jobs/{job_id}/stages/assets/manual-images"

            # Wrong id, wrong type, disguised HTML, and oversize are all refused
            # before anything is stored.
            assert client.post(f"{base}/scene_009", content=PNG, headers={"Content-Type": "image/png"}).status_code == 422
            assert client.post(f"{base}/scene_001", content=PNG, headers={"Content-Type": "text/html"}).status_code == 415
            assert client.post(f"{base}/scene_001", content=b"<html>", headers={"Content-Type": "image/png"}).status_code == 415
            big = PNG + b"\x00" * (8 * 1024 * 1024)
            assert client.post(f"{base}/scene_001", content=big, headers={"Content-Type": "image/png"}).status_code == 413
            assert client.post(f"{base}/skip", json={"ids": ["chapter_01"]}).status_code == 422
            assert client.get(f"/api/jobs/{job_id}").json()["status"] == "awaiting_manual_input"

            uploaded = client.post(f"{base}/chapter_01", content=PNG, headers={"Content-Type": "image/png"})
            assert uploaded.status_code == 200
            manual = next(s for s in uploaded.json()["stages"] if s["name"] == "assets")["output"]["manual"]
            assert manual["missing"] == ["scene_001"]
            assert uploaded.json()["status"] == "awaiting_manual_input"
            artifact = manual["images"]["chapter_01"]["artifact"]
            assert client.get(f"/api/jobs/{job_id}/artifacts/{artifact['id']}").content == PNG

            skipped = client.post(f"{base}/skip", json={})
            assert skipped.status_code == 200
            assert skipped.json()["status"] == "queued"
            job = wait(client, job_id, "failed")  # render is not connected in this fixture
            assets = next(s for s in job["stages"] if s["name"] == "assets")
            assert assets["status"] == "completed"
            assert [(i["id"], i.get("fallback")) for i in assets["output"]["images"]] == [
                ("chapter_01", None),
                ("scene_001", "chapter_hero"),
            ]
            assert client.post(f"{base}/skip", json={}).status_code == 409
    finally:
        settings.models.images_enabled = False


def test_manual_route_keeps_config_valid_and_mock_storyboard_has_chapters():
    from app.config import ModelConfig
    from app.providers import mock_storyboard
    from app.schemas import Storyboard

    settings = Settings()
    data = settings.models.model_dump()
    data["images_enabled"], data["routes"]["assets"] = True, "manual"
    assert ModelConfig.model_validate(data).routes["assets"] == "manual"
    data["routes"]["assets"] = "missing-role"
    with pytest.raises(ValueError, match="assets requires"):
        ModelConfig.model_validate(data)
    parsed = Storyboard.model_validate(mock_storyboard("Kafka"))
    assert [c.chapter_id for c in parsed.chapters] == ["chapter_01", "chapter_02"]
    assert json.dumps(mock_storyboard("Kafka"))
