"""Child-only heavy dependencies. Never import this module into the API server."""

import json
import math
import os
import re
import signal
import sys
from pathlib import Path

from .fidelity import fidelity

SENTENCE_SPLIT = r"(?<=[.!?])\s+|\n+"
SAMPLE_RATE = 24000


def _torch_device(device):
    """Map the config device onto a torch device string."""
    return "mps" if device == "metal" else device


def _sentences(text):
    return [s for s in re.split(SENTENCE_SPLIT, text) if s.strip()]


# JSON-schema keys llama.cpp unrolls into nested repetition groups. A
# ``maxLength`` of a few thousand exceeds its grammar limits and aborts the
# child natively, so these bounds stay with pydantic validation only.
GRAMMAR_UNSAFE_KEYS = ("minLength", "maxLength", "maxItems")


def grammar_schema(schema):
    """Copy of ``schema`` without the length bounds llama.cpp cannot compile."""
    if isinstance(schema, dict):
        return {
            key: grammar_schema(value)
            for key, value in schema.items()
            if key not in GRAMMAR_UNSAFE_KEYS
        }
    if isinstance(schema, list):
        return [grammar_schema(value) for value in schema]
    return schema


def _generate_json(model, spec, request, schemas):
    """Grammar-constrained decode, validated in-process; one repair pass on failure."""
    schema_cls = getattr(schemas, request["schema_name"])
    schema = grammar_schema(schema_cls.model_json_schema())
    messages = [dict(message) for message in request["messages"]]
    if spec.get("think_toggle") and messages and messages[0]["role"] == "system":
        messages[0]["content"] = f"{messages[0]['content']} {spec['think_toggle']}"
    error, content = None, ""
    for attempt in range(2):
        if error:
            messages = messages + [
                {"role": "assistant", "content": (content or "")[:4000]},
                {
                    "role": "user",
                    "content": f"Your previous output was invalid: {error}. Return corrected JSON only.",
                },
            ]
        response = model.create_chat_completion(
            messages=messages,
            max_tokens=spec["max_tokens"],
            temperature=request.get("temperature", 0.3),
            seed=request.get("seed", 42),
            response_format={"type": "json_object", "schema": schema},
        )
        choice = response["choices"][0]
        content = choice["message"]["content"]
        try:
            if choice.get("finish_reason") == "length":
                raise ValueError(
                    "Model output reached max_tokens; increase the limit or shorten the input"
                )
            return {
                "result": schema_cls.model_validate(
                    json.loads(content, strict=False)
                ).model_dump(),
                "repaired": attempt > 0,
            }
        except (ValueError, json.JSONDecodeError) as exc:
            error = f"{type(exc).__name__}: {str(exc)[:600]}"
    return {"error": error, "kind": "validation"}


def infer(spec, snapshot, payload, extras=None):
    root = Path(snapshot)
    extras = extras or {}
    runtime = spec["runtime"]
    if runtime == "llama_cpp":
        from llama_cpp import Llama

        from .. import schemas

        model = Llama(
            model_path=str(root / spec["filename"]),
            n_ctx=spec["context_size"],
            n_gpu_layers=spec["gpu_layers"]
            if spec["device"] in ("cuda", "metal")
            else 0,
            verbose=False,
        )
        try:
            return {
                "results": [
                    _generate_json(model, spec, request, schemas)
                    for request in payload["requests"]
                ]
            }
        finally:
            model.close()
    if runtime in ("kokoro", "qwen_tts"):
        import numpy as np
        import soundfile as sf

        device = _torch_device(spec["device"])
        if runtime == "kokoro":
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
                .to(device)
                .eval()
            )
            pipeline = KPipeline(lang_code="a", repo_id=spec["repo_id"], model=model)
            voice = spec["voice"]

            def synthesize(sentence):
                for text, _, audio in pipeline(
                    sentence,
                    voice=str(root / "voices" / f"{voice}.pt"),
                    speed=spec["speed"],
                ):
                    yield text, audio.cpu().numpy(), SAMPLE_RATE

        else:
            import torch
            from qwen_tts import Qwen3TTSModel

            model = Qwen3TTSModel.from_pretrained(
                str(root), device_map=device, dtype=torch.bfloat16
            )
            voice = spec["speaker"]

            def synthesize(sentence):
                wavs, rate = model.generate_custom_voice(
                    text=sentence, language="English", speaker=voice
                )
                yield sentence, np.asarray(wavs[0], dtype=np.float32), int(rate)

        pieces, segments, cursor, rate = [], [], 0.0, SAMPLE_RATE
        for sentence in _sentences(payload["text"]):
            for text, samples, rate in synthesize(sentence):
                duration = len(samples) / rate
                segments.append(
                    {"text": text, "start": cursor, "end": cursor + duration}
                )
                cursor += duration
                pieces.append(samples)
        if not pieces:
            raise ValueError("TTS produced no audio")
        sf.write(payload["output_path"], np.concatenate(pieces), rate)
        return {
            "duration_seconds": cursor,
            "sample_rate": rate,
            "segments": segments,
            "voice": voice,
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
        output = [
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
        ]
        transcript = " ".join(segment["text"] for segment in output)
        return {
            "segments": output,
            "duration_seconds": info.duration,
            "method": "asr_transcript",
            "fidelity": fidelity(payload.get("text", ""), transcript)
            if payload.get("text")
            else None,
        }
    if runtime == "ctc_aligner":
        import torch
        from ctc_forced_aligner import (
            generate_emissions,
            get_alignments,
            get_spans,
            load_alignment_model,
            load_audio,
            postprocess_results,
            preprocess_text,
        )

        device = spec["device"]
        model, tokenizer = load_alignment_model(
            device,
            model_path=str(root),
            dtype=torch.float16 if device == "cuda" else torch.float32,
        )
        waveform = load_audio(payload["audio_path"], model.dtype, model.device)
        emissions, stride = generate_emissions(model, waveform, batch_size=4)
        tokens, starred = preprocess_text(
            payload["text"], romanize=True, language="eng"
        )
        alignments, scores, blank = get_alignments(emissions, tokens, tokenizer)
        spans = get_spans(tokens, alignments, blank)
        words = postprocess_results(starred, spans, stride, scores)
        if not words:
            raise ValueError("Forced alignment produced no words")
        # Group aligned words back into the script's sentences.
        segments, cursor = [], 0
        for sentence in _sentences(payload["text"]):
            count = len(preprocess_text(sentence, romanize=True, language="eng")[1])
            chunk = words[cursor : cursor + count] or words[-1:]
            cursor += count
            segments.append(
                {
                    "text": sentence,
                    "start": chunk[0]["start"],
                    "end": chunk[-1]["end"],
                    "words": [
                        {"word": w["text"], "start": w["start"], "end": w["end"]}
                        for w in chunk
                    ],
                }
            )
        mean_score = sum(float(w.get("score", 0.0)) for w in words) / len(words)
        return {
            "segments": segments,
            "duration_seconds": words[-1]["end"],
            "method": "forced_alignment",
            # Scores are mean log-probabilities; exp maps them onto 0–1.
            "fidelity": max(0.0, min(1.0, math.exp(mean_score))),
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
    if runtime in ("diffusers", "diffusers_gguf"):
        import torch

        if spec["device"] != "cuda" or not torch.cuda.is_available():
            raise ValueError(
                "Image generation requires the configured CUDA host; disable images on CPU hosts"
            )
        generator = torch.Generator("cpu").manual_seed(42)
        if runtime == "diffusers":
            from diffusers import StableDiffusionXLPipeline

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
                generator=generator,
            ).images[0]
        else:
            from diffusers import (
                FluxPipeline,
                FluxTransformer2DModel,
                GGUFQuantizationConfig,
            )
            from transformers import T5EncoderModel

            base = Path(extras["base"]["snapshot"])
            encoder = extras["text_encoder"]
            quantization = GGUFQuantizationConfig(compute_dtype=torch.bfloat16)
            transformer = FluxTransformer2DModel.from_single_file(
                str(root / spec["filename"]),
                quantization_config=quantization,
                config=str(base),
                subfolder="transformer",
                torch_dtype=torch.bfloat16,
            )
            text_encoder_2 = T5EncoderModel.from_pretrained(
                encoder["snapshot"],
                gguf_file=encoder["filename"],
                torch_dtype=torch.bfloat16,
                local_files_only=True,
            )
            pipeline = FluxPipeline.from_pretrained(
                str(base),
                transformer=transformer,
                text_encoder_2=text_encoder_2,
                torch_dtype=torch.bfloat16,
                local_files_only=True,
            )
            pipeline.enable_model_cpu_offload()
            pipeline.enable_vae_slicing()
            pipeline.enable_vae_tiling()
            image = pipeline(
                payload["prompt"],
                width=768,
                height=768,
                num_inference_steps=spec["steps"],
                guidance_scale=0.0,
                max_sequence_length=256,
                generator=generator,
            ).images[0]
        image.save(payload["output_path"])
        return {"width": 768, "height": 768, "prompt": payload["prompt"], "seed": 42}
    raise ValueError(f"Unsupported runtime: {runtime}")


def _fail(result_path, message, kind="inference"):
    result_path.write_text(json.dumps({"error": message[:1200], "kind": kind}))
    sys.exit(1)


if __name__ == "__main__":
    result_path = Path(sys.argv[2])
    try:
        # Linux releases child GPU memory even if the parent is killed abruptly.
        if sys.platform == "linux":
            import ctypes

            if ctypes.CDLL(None).prctl(1, signal.SIGKILL) != 0:
                raise RuntimeError(
                    "Could not set the local runtime parent-death signal"
                )
        expected_parent = os.getenv("ORCHESTRATOR_PARENT_PID")
        if expected_parent and os.getppid() != int(expected_parent):
            _fail(
                result_path,
                "Local runtime parent process is gone; refusing to load models",
                "configuration",
            )
        request = json.loads(Path(sys.argv[1]).read_text())
        result_path.write_text(json.dumps(infer(**request), allow_nan=False))
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 - serialize failures at the process boundary
        _fail(
            result_path,
            f"{type(exc).__name__}: {str(exc)[:1200]}",
            "configuration"
            if isinstance(exc, (ImportError, FileNotFoundError))
            else "inference",
        )
