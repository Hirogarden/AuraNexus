import json
from pathlib import Path

import pytest

from core.inference import InferenceEngine


class _MemoryStats:
    def __init__(self, available: int) -> None:
        self.available = available


class _FakeModelMissingSamplers:
    def __init__(self) -> None:
        self.last_call = None

    def create_completion(self, prompt: str, max_tokens: int, temperature: float, stream: bool):
        self.last_call = {
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": stream,
        }
        yield {"choices": [{"text": "should not be reached"}]}


class _FakeModelWithKwargs:
    def __init__(self) -> None:
        self.last_call = None

    def create_completion(self, **kwargs):
        self.last_call = kwargs
        yield {"choices": [{"text": "ok"}]}


def test_generate_falls_back_when_sampler_support_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "inference_config.json"
    model_path = tmp_path / "model.gguf"

    model_path.write_text("not-a-real-model", encoding="utf-8")
    config_path.write_text(
        json.dumps(
            {
                "required_ram_buffer_mb": 2048.0,
                "n_gpu_layers": 0,
                "ctx_size": 1024,
                "sampling": {
                    "temperature": 0.7,
                    "max_tokens": 64,
                    "min_p": 0.05,
                    "dry_multiplier": 0.8,
                    "dry_base": 1.75,
                    "dry_allowed_length": 2,
                    "xtc_probability": 0.1,
                    "xtc_threshold": 0.1,
                },
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "core.inference.psutil.virtual_memory",
        lambda: _MemoryStats(available=8 * 1024 * 1024 * 1024),
    )

    engine = InferenceEngine(model_path=model_path, config_path=config_path)
    fake_model = _FakeModelMissingSamplers()
    engine.model = fake_model

    first_chunk = next(engine.generate("hello"))
    assert first_chunk == "should not be reached"
    assert fake_model.last_call is not None
    assert set(fake_model.last_call.keys()) == {"prompt", "max_tokens", "temperature", "stream"}


def test_generate_uses_runtime_overrides(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "inference_config.json"
    model_path = tmp_path / "model.gguf"

    model_path.write_text("not-a-real-model", encoding="utf-8")
    config_path.write_text(
        json.dumps(
            {
                "required_ram_buffer_mb": 2048.0,
                "n_gpu_layers": 0,
                "ctx_size": 1024,
                "sampling": {
                    "temperature": 0.7,
                    "max_tokens": 64,
                    "min_p": 0.05,
                    "dry_multiplier": 0.8,
                    "dry_base": 1.75,
                    "dry_allowed_length": 2,
                    "xtc_probability": 0.1,
                    "xtc_threshold": 0.1,
                },
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "core.inference.psutil.virtual_memory",
        lambda: _MemoryStats(available=8 * 1024 * 1024 * 1024),
    )

    engine = InferenceEngine(model_path=model_path, config_path=config_path)
    fake_model = _FakeModelWithKwargs()
    engine.model = fake_model
    engine.set_generation_overrides(max_tokens=12, temperature=0.2)

    first_chunk = next(engine.generate("hello"))
    assert first_chunk == "ok"
    assert fake_model.last_call is not None
    assert fake_model.last_call["max_tokens"] == 12
    assert fake_model.last_call["temperature"] == 0.2
