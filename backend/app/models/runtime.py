"""Child-only heavy dependencies. Never import this module into the API server."""

import json
import os
import re
import signal
import sys
from pathlib import Path


def infer(spec, snapshot, payload):
    root = Path(snapshot)
    runtime = spec["runtime"]
    if runtime == "llama_cpp":
        from llama_cpp import Llama

        model = Llama(
            model_path=str(root / spec["filename"]),
            n_ctx=spec["context_size"],
            n_gpu_layers=spec["gpu_layers"] if spec["device"] == "cuda" else 0,
            verbose=False,
        )
        try:
            response = model.create_chat_completion(
                messages=payload["messages"],
                max_tokens=spec["max_tokens"],
                temperature=0.3,
                seed=42,
                response_format={"type": "json_object", "schema": payload["schema"]},
            )
            choice = response["choices"][0]
            if choice.get("finish_reason") == "length":
                raise ValueError(
                    "Model output reached max_tokens; increase the limit or shorten the input"
                )
            return {"result": json.loads(choice["message"]["content"])}
        finally:
            model.close()
    if runtime == "kokoro":
        import numpy as np
        import soundfile as sf
        import spacy

        # Prevent Misaki's automatic language-model download in an inference job.
        spacy.load("en_core_web_sm")
        from kokoro import KModel, KPipeline

        model = (
            KModel(
                repo_id=spec["repo_id"],
                config=str(root / "config.json"),
                model=str(root / spec["filename"]),
            )
            .to(spec["device"])
            .eval()
        )
        pipeline = KPipeline(lang_code="a", repo_id=spec["repo_id"], model=model)
        pieces, segments, cursor = [], [], 0.0
        for sentence in re.split(r"(?<=[.!?])\s+|\n+", payload["text"]):
            if not sentence.strip():
                continue
            for text, _, audio in pipeline(
                sentence,
                voice=str(root / "voices" / f"{spec['voice']}.pt"),
                speed=spec["speed"],
            ):
                samples = audio.cpu().numpy()
                duration = len(samples) / 24000
                segments.append(
                    {"text": text, "start": cursor, "end": cursor + duration}
                )
                cursor += duration
                pieces.append(samples)
        if not pieces:
            raise ValueError("TTS produced no audio")
        sf.write(payload["output_path"], np.concatenate(pieces), 24000)
        return {
            "duration_seconds": cursor,
            "sample_rate": 24000,
            "segments": segments,
            "voice": spec["voice"],
            "speed": spec["speed"],
        }
    if runtime == "whisper":
        from faster_whisper import WhisperModel

        model = WhisperModel(
            str(root),
            device=spec["device"],
            compute_type="int8" if spec["device"] == "cpu" else "float16",
            local_files_only=True,
        )
        segments, info = model.transcribe(
            payload["audio_path"], language="en", word_timestamps=True, beam_size=5
        )
        return {
            "segments": [
                {
                    "text": segment.text,
                    "start": segment.start,
                    "end": segment.end,
                    "words": [
                        {"word": word.word, "start": word.start, "end": word.end}
                        for word in (segment.words or [])
                    ],
                }
                for segment in segments
            ],
            "duration_seconds": info.duration,
        }
    if runtime == "sentence_transformers":
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer(
            str(root), device="cpu", local_files_only=True, trust_remote_code=False
        )
        return {
            "embeddings": model.encode(
                payload["texts"], normalize_embeddings=True
            ).tolist()
        }
    if runtime == "diffusers":
        import torch
        from diffusers import StableDiffusionXLPipeline

        if spec["device"] != "cuda" or not torch.cuda.is_available():
            raise ValueError(
                "SDXL requires the configured CUDA host; disable images on CPU hosts"
            )
        pipeline = StableDiffusionXLPipeline.from_pretrained(
            str(root),
            torch_dtype=torch.float16,
            variant="fp16",
            use_safetensors=True,
            local_files_only=True,
        )
        pipeline.enable_model_cpu_offload()
        pipeline.enable_vae_slicing()
        pipeline.enable_vae_tiling()
        image = pipeline(
            payload["prompt"],
            width=768,
            height=768,
            num_inference_steps=25,
            generator=torch.Generator("cpu").manual_seed(42),
        ).images[0]
        image.save(payload["output_path"])
        return {"width": 768, "height": 768, "prompt": payload["prompt"], "seed": 42}
    raise ValueError(f"Unsupported runtime: {runtime}")


if __name__ == "__main__":
    # Linux releases child GPU memory even if the parent is killed abruptly.
    if sys.platform == "linux":
        import ctypes

        if ctypes.CDLL(None).prctl(1, signal.SIGKILL) != 0:
            raise RuntimeError("Could not set the local runtime parent-death signal")
    expected_parent = os.getenv("ORCHESTRATOR_PARENT_PID")
    if expected_parent and os.getppid() != int(expected_parent):
        sys.exit(1)
    request = json.loads(Path(sys.argv[1]).read_text())
    result_path = Path(sys.argv[2])
    try:
        result_path.write_text(json.dumps(infer(**request), allow_nan=False))
    except Exception as exc:  # noqa: BLE001 - serialize failures at the process boundary
        result_path.write_text(
            json.dumps(
                {
                    "error": f"{type(exc).__name__}: {str(exc)[:1200]}",
                    "kind": "configuration"
                    if isinstance(exc, (ImportError, FileNotFoundError))
                    else "inference",
                }
            )
        )
        sys.exit(1)
