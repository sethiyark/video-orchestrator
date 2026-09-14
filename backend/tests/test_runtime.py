"""The inference child with fake heavy libraries: no weights, no GPU."""

import json
import os
import subprocess
import sys
import types
from typing import ClassVar
from unittest.mock import patch

import pytest

from app.config import ROOT, Settings
from app.models.fidelity import fidelity, word_error_rate
from app.models.runtime import grammar_schema, infer


class FakeLlama:
    instances: ClassVar[list] = []
    responses: ClassVar[list] = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.calls = []
        self.closed = False
        FakeLlama.instances.append(self)

    def create_chat_completion(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        content = self.responses.pop(0)
        finish = "length" if content == "LENGTH" else "stop"
        return {"choices": [{"message": {"content": content}, "finish_reason": finish}]}

    def close(self):
        self.closed = True


@pytest.fixture
def llama(monkeypatch):
    FakeLlama.instances = []
    module = types.ModuleType("llama_cpp")
    module.Llama = FakeLlama
    monkeypatch.setitem(sys.modules, "llama_cpp", module)
    return FakeLlama


def spec(**overrides):
    return {**Settings().models.models["quality"].model_dump(), **overrides}


def request(seed=1):
    return {
        "messages": [
            {"role": "system", "content": "Critic"},
            {"role": "user", "content": "{}"},
        ],
        "schema_name": "Critic",
        "seed": seed,
        "temperature": 0.5,
    }


CRITIC = '{"score": 9, "issues": [], "required_changes": [], "optional_changes": []}'


def test_batch_loads_once_and_appends_think_toggle(llama, tmp_path):
    FakeLlama.responses = [CRITIC] * 3
    out = infer(
        spec(device="metal", gpu_layers=-1),
        str(tmp_path),
        {"requests": [request(1), request(2), request(3)]},
    )
    assert [item["result"]["score"] for item in out["results"]] == [9, 9, 9]
    (model,) = FakeLlama.instances
    assert model.kwargs["n_gpu_layers"] == -1 and model.closed
    messages, kwargs = model.calls[0]
    assert messages[0]["content"].endswith("/no_think")
    assert kwargs["seed"] == 1 and kwargs["temperature"] == 0.5
    assert [call[1]["seed"] for call in model.calls] == [1, 2, 3]


def test_think_toggle_renders_template_with_thinking_disabled(
    llama, monkeypatch, tmp_path
):
    # Under a JSON grammar Qwen3 ignores /no_think and writes its reasoning into
    # the first string field; the template switch pre-fills an empty think block.
    rendered = []
    chat_format = types.ModuleType("llama_cpp.llama_chat_format")

    class Formatter:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def __call__(self, **kwargs):
            rendered.append(kwargs)

    chat_format.Jinja2ChatFormatter = Formatter
    chat_format.chat_formatter_to_chat_completion_handler = lambda formatter: formatter
    monkeypatch.setitem(sys.modules, "llama_cpp.llama_chat_format", chat_format)

    class Tokens:
        def token_get_text(self, token):
            return {1: "<|im_end|>"}[token]

    class TemplatedLlama(FakeLlama):
        metadata: ClassVar[dict] = {
            "tokenizer.chat_template": "{% if enable_thinking is false %}{% endif %}"
        }
        _model = Tokens()

        def token_eos(self):
            return 1

        def token_bos(self):
            return -1

    monkeypatch.setattr(sys.modules["llama_cpp"], "Llama", TemplatedLlama)
    FakeLlama.responses = [CRITIC, CRITIC]
    infer(spec(), str(tmp_path), {"requests": [request()]})
    model = FakeLlama.instances[-1]
    model.chat_handler(messages=[])
    assert rendered == [{"messages": [], "enable_thinking": False}]
    assert model.calls[0][0][0]["content"].endswith("/no_think")

    FakeLlama.instances = []
    infer(spec(think_toggle=None), str(tmp_path), {"requests": [request()]})
    assert not hasattr(FakeLlama.instances[-1], "chat_handler")


def test_grammar_schema_keeps_only_compilable_bounds(llama, tmp_path):
    from app import schemas

    full = schemas.Research.model_json_schema()
    assert full["properties"]["summary"]["maxLength"] == 2000
    stripped = grammar_schema(full)
    # llama.cpp aborts on a 2000-char repetition; pydantic still enforces it.
    assert "maxLength" not in stripped["properties"]["summary"]
    claim = stripped["$defs"]["Claim"]["properties"]
    assert claim["text"]["maxLength"] == 1000 and "maxLength" not in claim["quote"]
    assert stripped["properties"]["claims"]["maxItems"] == 30

    FakeLlama.responses = [CRITIC]
    infer(spec(), str(tmp_path), {"requests": [request()]})
    (model,) = FakeLlama.instances
    sent = model.calls[0][1]["response_format"]["schema"]["properties"]
    # Critic lists are bounded during decoding, so a looping critic cannot run
    # to max_tokens.
    assert sent["issues"]["maxItems"] == 6
    assert sent["issues"]["items"]["maxLength"] == 300
    with pytest.raises(ValueError):
        schemas.Research.model_validate({"summary": "x" * 2001, "claims": []})


def test_cpu_device_uses_no_gpu_layers(llama, tmp_path):
    FakeLlama.responses = [CRITIC]
    infer(
        spec(device="cpu", gpu_layers=-1, think_toggle=None),
        str(tmp_path),
        {"requests": [request()]},
    )
    model = FakeLlama.instances[-1]
    assert model.kwargs["n_gpu_layers"] == 0
    assert model.calls[0][0][0]["content"] == "Critic"


def test_invalid_json_is_repaired_in_child(llama, tmp_path):
    FakeLlama.responses = ['{"score": 42}', CRITIC]
    out = infer(spec(), str(tmp_path), {"requests": [request()]})
    assert out["results"][0]["repaired"] is True
    messages, _ = FakeLlama.instances[-1].calls[1]
    assert messages[-1]["role"] == "user" and "invalid" in messages[-1]["content"]
    assert messages[-2] == {"role": "assistant", "content": '{"score": 42}'}


def test_repair_failure_is_reported_not_raised(llama, tmp_path):
    FakeLlama.responses = ["LENGTH", "not json"]
    out = infer(spec(), str(tmp_path), {"requests": [request()]})
    assert out["results"][0]["kind"] == "validation"
    assert "JSON" in out["results"][0]["error"]
    assert len(FakeLlama.instances[-1].calls) == 2


def test_truncated_output_retries_fresh_not_replayed(llama, tmp_path):
    FakeLlama.responses = ["LENGTH", CRITIC]
    out = infer(spec(), str(tmp_path), {"requests": [request(seed=7)]})
    assert out["results"][0]["repaired"] is True
    first, second = FakeLlama.instances[-1].calls
    # The looping output is not fed back; the retry changes seed and penalises repeats.
    assert all(m["role"] != "assistant" for m in second[0])
    assert second[0][:2] == first[0][:2] and "output limit" in second[0][-1]["content"]
    assert (first[1]["seed"], second[1]["seed"]) == (7, 8)
    assert "repeat_penalty" not in first[1] and second[1]["repeat_penalty"] == 1.1

    FakeLlama.responses = ["LENGTH", "LENGTH"]
    out = infer(spec(), str(tmp_path), {"requests": [request()]})
    assert "max_tokens" in out["results"][0]["error"]


def test_leaked_reasoning_is_rejected_for_repair(llama, tmp_path):
    from app.schemas import Critic, Script

    leak = "Okay, let's tackle this query. The user provided a detailed JSON structure."
    for text in (
        leak,
        "<think>plan</think>DNS maps names to addresses.",
        "First, I need to parse the JSON to understand it properly.",
    ):
        with pytest.raises(ValueError, match="reasoning"):
            Script.model_validate({"text": text, "claim_ids": ["c1"]})
    Script.model_validate(
        {
            "text": "So DNS maps names to addresses. The user wants a fast page.",
            "claim_ids": ["c1"],
        }
    )
    with pytest.raises(ValueError):
        Critic.model_validate(
            {
                "score": 1,
                "issues": ["x"] * 7,
                "required_changes": [],
                "optional_changes": [],
            }
        )

    good = json.dumps(
        {"text": "DNS maps domain names to IP addresses.", "claim_ids": ["c1"]}
    )
    FakeLlama.responses = [json.dumps({"text": leak, "claim_ids": ["c1"]}), good]
    payload = {**request(), "schema_name": "Script"}
    out = infer(spec(), str(tmp_path), {"requests": [payload]})
    assert out["results"][0]["repaired"] is True
    assert "reasoning" in FakeLlama.instances[-1].calls[1][0][-1]["content"]


def test_whisper_reports_fidelity(tmp_path, monkeypatch):
    class Segment:
        def __init__(self, text):
            self.text, self.start, self.end, self.words = text, 0.0, 1.0, []

    class FakeWhisper:
        def __init__(self, *args, **kwargs):
            pass

        def transcribe(self, *args, **kwargs):
            return [Segment("DNS maps domain names")], types.SimpleNamespace(
                duration=1.0
            )

    module = types.ModuleType("faster_whisper")
    module.WhisperModel = FakeWhisper
    monkeypatch.setitem(sys.modules, "faster_whisper", module)
    out = infer(
        Settings().models.models["alignment"].model_dump(),
        str(tmp_path),
        {"audio_path": "x.wav", "text": "DNS maps domain names to addresses"},
    )
    assert out["method"] == "asr_transcript"
    assert out["fidelity"] == pytest.approx(1 - 2 / 6)


def test_word_error_rate():
    assert word_error_rate("DNS maps names.", "dns maps names") == 0
    assert word_error_rate("a b c d", "a b x d") == pytest.approx(0.25)
    assert word_error_rate("a b", "") == 1
    assert fidelity("hello world", "hello there world") == pytest.approx(0.5)


def test_unsupported_runtime_and_cuda_guard(tmp_path):
    with pytest.raises(ValueError, match="Unsupported"):
        infer({"runtime": "nope"}, str(tmp_path), {})
    torch = types.ModuleType("torch")
    torch.cuda = types.SimpleNamespace(is_available=lambda: False)
    with (
        patch.dict(sys.modules, {"torch": torch}),
        pytest.raises(ValueError, match="CUDA host"),
    ):
        infer(
            Settings().models.models["images"].model_dump(),
            str(tmp_path),
            {"prompt": "x", "output_path": "x.png"},
        )


def test_sdxl_runs_on_metal(tmp_path, monkeypatch):
    saved = []

    class Image:
        def save(self, path):
            saved.append(path)

    class Pipeline:
        @classmethod
        def from_pretrained(cls, *args, **kwargs):
            return cls()

        def to(self, device):
            self.device = device
            return self

        def enable_attention_slicing(self):
            pass

        def enable_vae_slicing(self):
            pass

        def __call__(self, prompt, **kwargs):
            assert prompt == "diagram"
            assert kwargs["guidance_scale"] == 0.0
            assert kwargs["num_inference_steps"] == 4
            return types.SimpleNamespace(images=[Image()])

    torch = types.ModuleType("torch")
    torch.float16 = object()
    torch.float32 = object()
    torch.Generator = lambda device: types.SimpleNamespace(
        manual_seed=lambda seed: None
    )
    torch.cuda = types.SimpleNamespace(is_available=lambda: False)
    torch.backends = types.SimpleNamespace(
        mps=types.SimpleNamespace(is_available=lambda: True)
    )
    diffusers = types.ModuleType("diffusers")
    diffusers.StableDiffusionXLPipeline = Pipeline
    monkeypatch.setitem(sys.modules, "torch", torch)
    monkeypatch.setitem(sys.modules, "diffusers", diffusers)
    out = infer(
        {"runtime": "diffusers", "device": "metal", "steps": 4},
        str(tmp_path),
        {"prompt": "diagram", "output_path": str(tmp_path / "out.png")},
    )
    assert out == {
        "width": 768,
        "height": 768,
        "prompt": "diagram",
        "seed": 42,
    }
    assert saved == [str(tmp_path / "out.png")]


def test_runtime_main_writes_json_when_parent_pid_mismatches(tmp_path):
    request = tmp_path / "request.json"
    result = tmp_path / "result.json"
    request.write_text(
        json.dumps(
            {"spec": {"runtime": "nope"}, "snapshot": str(tmp_path), "payload": {}}
        )
    )
    env = {**os.environ, "ORCHESTRATOR_PARENT_PID": "999999"}
    completed = subprocess.run(
        [sys.executable, "-m", "app.models.runtime", str(request), str(result)],
        cwd=ROOT,
        env=env,
        check=False,
    )
    assert completed.returncode == 1
    failure = json.loads(result.read_text())
    assert failure["kind"] == "configuration"
    assert "parent process is gone" in failure["error"]
