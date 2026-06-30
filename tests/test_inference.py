import json
from pathlib import Path

import pytest

from core.inference import InferenceEngine


class _MemoryStats:
    def __init__(self, available: int) -> None:
        self.available = available


class _FakeModelMissingSamplers:
    def create_completion(self, prompt: str, max_tokens: int, temperature: float, stream: bool):
        yield {"choices": [{"text": "should not be reached"}]}


def test_generate_fails_when_sampler_support_missing(
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
    engine.model = _FakeModelMissingSamplers()

    with pytest.raises(RuntimeError, match="does not support required sampler parameters"):
        next(engine.generate("hello"))
