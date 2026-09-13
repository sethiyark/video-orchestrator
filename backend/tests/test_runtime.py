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


def test_grammar_schema_drops_length_bounds_pydantic_still_enforces(llama, tmp_path):
    from app import schemas

    full = schemas.Research.model_json_schema()
    assert full["properties"]["summary"]["maxLength"] == 2000
    stripped = json.dumps(grammar_schema(full))
    for key in ("minLength", "maxLength", "maxItems"):
        assert key not in stripped

    FakeLlama.responses = [CRITIC]
    infer(spec(), str(tmp_path), {"requests": [request()]})
    (model,) = FakeLlama.instances
    sent = json.dumps(model.calls[0][1]["response_format"]["schema"])
    assert "maxLength" not in sent
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
    assert (
        "max_tokens" in out["results"][0]["error"]
        or "JSON" in out["results"][0]["error"]
    )
    assert len(FakeLlama.instances[-1].calls) == 2


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
