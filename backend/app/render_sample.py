"""Offline two-minute sample: fixed scenes and a quiet calibration tone, no models."""

import asyncio
import math
import struct
import tempfile
import wave
from pathlib import Path

from .artifacts import Artifacts
from .rendering import RemotionRenderer


async def main() -> None:
    artifacts = Artifacts(Path(__file__).resolve().parents[1] / "data/artifacts")
    scenes = [
        {
            "component": "DefinitionCard",
            "props": {"title": "DNS", "body": "DNS maps domain names to IP addresses."},
        },
        {
            "component": "AnimatedFlowDiagram",
            "props": {
                "title": "A DNS query",
                "nodes": ["Browser", "Resolver", "Authoritative server", "IP address"],
            },
        },
        {
            "component": "BulletReveal",
            "props": {
                "title": "Remember",
                "bullets": [
                    "Names are easier to remember",
                    "Resolvers cache answers",
                    "Records have a time to live",
                ],
            },
        },
    ]
    segments = []
    for i, scene in enumerate(scenes):
        scene.update(
            scene_id=f"scene_{i + 1:03d}",
            narration_text=f"Sample scene {i + 1}",
            duration_seconds=40,
        )
        segments.append(
            {"text": scene["narration_text"], "start": i * 40, "end": (i + 1) * 40}
        )
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / "tone.wav"
        with wave.open(str(path), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(8000)
            second = b"".join(
                struct.pack("<h", int(250 * math.sin(2 * math.pi * 220 * i / 8000)))
                for i in range(8000)
            )
            for _ in range(120):
                wav.writeframes(second)
        audio = artifacts.adopt("render-sample", path)
    outputs = {
        "storyboard": {"scenes": scenes},
        "narration": {"audio": audio},
        "alignment": {"segments": segments},
        "assets": {},
    }
    job = {
        "id": "render-sample",
        "stages": [{"name": key, "output": value} for key, value in outputs.items()],
    }
    result = await RemotionRenderer().render(job, artifacts, None)
    print(artifacts.resolve(job["id"], result["video"]["id"]))


if __name__ == "__main__":
    asyncio.run(main())
