"""Offline chaptered sample: every storyboard component over gradient plates and
a quiet calibration tone. No models, no network; exercises the real renderer."""

import asyncio
import math
import struct
import tempfile
import wave
import zlib
from pathlib import Path

from .artifacts import Artifacts
from .rendering import RemotionRenderer

# (component, props) in playback order; the last scene must be an Outro.
SCENES = [
    ("ChapterTitle", {"title": "What DNS does", "subtitle": "Names in, addresses out"}),
    (
        "DefinitionCard",
        {"title": "DNS", "body": "DNS maps domain names to IP addresses."},
    ),
    (
        "AnimatedFlowDiagram",
        {
            "title": "A DNS query",
            "nodes": ["Browser", "Resolver", "Authoritative server", "IP address"],
        },
    ),
    (
        "IconGrid",
        {
            "title": "Who is involved",
            "items": [
                {"icon": "browser", "label": "Browser"},
                {"icon": "server", "label": "Resolver"},
                {"icon": "database", "label": "Zone data"},
                {"icon": "globe", "label": "Root servers"},
                {"icon": "clock", "label": "TTL cache"},
                {"icon": "shield", "label": "DNSSEC"},
            ],
        },
    ),
    (
        "CodeBlock",
        {
            "title": "Resolving a name in Python",
            "language": "python",
            "code": (
                "import socket\n\n"
                "def resolve(name: str) -> str:\n"
                "    # Ask the system resolver\n"
                "    return socket.gethostbyname(name)\n\n"
                'print(resolve("example.com"))'
            ),
            "highlight_lines": [5],
        },
    ),
    (
        "Terminal",
        {
            "title": "The same lookup from a shell",
            "lines": [
                {"kind": "command", "text": "dig +short example.com"},
                {"kind": "output", "text": "93.184.216.34"},
                {"kind": "command", "text": "dig +short example.com AAAA"},
                {"kind": "output", "text": "2606:2800:220:1:248:1893:25c8:1946"},
            ],
        },
    ),
    (
        "Comparison",
        {
            "title": "Recursive vs iterative",
            "left": {
                "label": "Recursive resolver",
                "points": [
                    "Does the whole walk for you",
                    "Caches answers",
                    "Run by your ISP or a public service",
                ],
            },
            "right": {
                "label": "Iterative lookup",
                "points": [
                    "Client follows referrals itself",
                    "No shared cache",
                    "Rare outside resolvers",
                ],
            },
        },
    ),
    (
        "StatCounter",
        {
            "title": "Why caching matters",
            "stats": [
                {"value": "300s", "label": "Typical TTL"},
                {"value": "13", "label": "Root server identities"},
                {"value": "1.2M", "label": "Queries per second, one resolver"},
            ],
        },
    ),
    (
        "Timeline",
        {
            "title": "Life of a record",
            "events": [
                {"label": "1983", "text": "DNS specified in RFC 882"},
                {"label": "1987", "text": "RFC 1034 and 1035"},
                {"label": "2005", "text": "DNSSEC standardised"},
                {"label": "2018", "text": "DNS over HTTPS"},
            ],
        },
    ),
    (
        "Callout",
        {
            "title": "In the words of the standard",
            "quote": "The domain system provides a mechanism for naming resources",
            "claim_id": "c1",
        },
    ),
    (
        "BulletReveal",
        {
            "title": "Remember",
            "bullets": [
                "Names are easier to remember",
                "Resolvers cache answers",
                "Records have a time to live",
            ],
        },
    ),
    (
        "ImagePan",
        {
            "title": "A resolver at work",
            "prompt": "A labeled diagram of a resolver answering a browser",
        },
    ),
    (
        "Outro",
        {
            "title": "Recap",
            "takeaways": [
                "DNS turns names into addresses",
                "Caching keeps it fast",
                "TTL bounds staleness",
            ],
            "next_topic": "How TLS handshakes work",
        },
    ),
]
CHAPTERS = [
    ("What DNS does", "Names in, addresses out", (0, 3)),
    ("Under the hood", "Code, shells and caches", (4, 8)),
    ("Putting it together", "Evidence and takeaways", (9, 12)),
]
SECONDS_PER_SCENE = 9
COLORS = [(24, 60, 92), (70, 30, 90), (20, 80, 70), (90, 50, 20)]


def gradient_png(path: Path, color: tuple, width: int = 640, height: int = 360) -> None:
    """A 16:9 gradient plate written with zlib only (no imaging library)."""
    rows = []
    for y in range(height):
        row = bytearray([0])
        for x in range(width):
            t = (x / width + y / height) / 2
            row += bytes(min(255, int(c * (0.4 + 0.9 * t))) for c in color)
        rows.append(bytes(row))

    def chunk(kind, data):
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(b"".join(rows), 6))
        + chunk(b"IEND", b"")
    )


async def main() -> None:
    artifacts = Artifacts(Path(__file__).resolve().parents[1] / "data/artifacts")
    job_id = "render-sample"
    scenes, segments = [], []
    for index, (component, props) in enumerate(SCENES):
        text = f"Sample scene {index + 1} narrates {props['title'].lower()} for a few seconds."
        scenes.append(
            {
                "scene_id": f"scene_{index + 1:03d}",
                "narration_text": text,
                "duration_seconds": SECONDS_PER_SCENE,
                "image_prompt": f"Illustration for {props['title']}",
                "component": component,
                "props": props,
            }
        )
        start = index * SECONDS_PER_SCENE
        tokens = text.split()
        step = (SECONDS_PER_SCENE - 1.5) / len(tokens)
        segments.append(
            {
                "text": text,
                "start": start,
                "end": start + SECONDS_PER_SCENE,
                "words": [
                    {
                        "word": word,
                        "start": start + i * step,
                        "end": start + (i + 1) * step,
                    }
                    for i, word in enumerate(tokens)
                ],
            }
        )
    chapters = [
        {
            "chapter_id": f"chapter_{index + 1:02d}",
            "title": title,
            "tagline": tagline,
            "first_scene": scenes[first]["scene_id"],
            "last_scene": scenes[last]["scene_id"],
            "hero_prompt": f"A wide illustration for {title}",
            "accent": index,
        }
        for index, (title, tagline, (first, last)) in enumerate(CHAPTERS)
    ]
    total = len(SCENES) * SECONDS_PER_SCENE
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
            for _ in range(total):
                wav.writeframes(second)
        audio = artifacts.adopt(job_id, path)
        images = []
        for index, chapter in enumerate(chapters):
            plate = Path(temporary) / f"{chapter['chapter_id']}.png"
            gradient_png(plate, COLORS[index % len(COLORS)])
            images.append(
                {
                    "id": chapter["chapter_id"],
                    "kind": "hero",
                    "artifact": artifacts.adopt(job_id, plate),
                }
            )
        for index, scene in enumerate(scenes):
            plate = Path(temporary) / f"{scene['scene_id']}.png"
            gradient_png(plate, COLORS[(index + 1) % len(COLORS)])
            images.append(
                {
                    "id": scene["scene_id"],
                    "kind": "scene",
                    "artifact": artifacts.adopt(job_id, plate),
                }
            )
    outputs = {
        "storyboard": {"scenes": scenes, "chapters": chapters},
        "narration": {"audio": audio},
        "alignment": {"segments": segments},
        "assets": {"images": images},
    }
    job = {
        "id": job_id,
        "title": "DNS sample",
        "stages": [{"name": key, "output": value} for key, value in outputs.items()],
    }
    result = await RemotionRenderer().render(job, artifacts, None)
    print(artifacts.resolve(job["id"], result["video"]["id"]))


if __name__ == "__main__":
    asyncio.run(main())
