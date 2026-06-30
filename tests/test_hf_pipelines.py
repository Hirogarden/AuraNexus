import json
from pathlib import Path

import pytest

from tools.hf_pipelines import HFPipelineRouter, HFPipelineError


class _StubSandbox:
    def __init__(self, root: Path):
        self.root = root

    def sanitize_path(self, relative_path: str):
        return self.root / relative_path


class _FakePipeline:
    def __init__(self):
        self.calls = []

    def __call__(self, text: str, **kwargs):
        self.calls.append((text, kwargs))
        return [{"label": "POSITIVE", "score": 0.99}]


def test_run_text_task_with_factory_and_audit_log(tmp_path: Path) -> None:
    sandbox = _StubSandbox(tmp_path)
    created = {}

    def factory(task: str, model=None, device=-1):
        created["task"] = task
        created["model"] = model
        created["device"] = device
        created["pipeline"] = _FakePipeline()
        return created["pipeline"]

    router = HFPipelineRouter(sandbox=sandbox, pipeline_factory=factory)
    result = router.run_text_task(
        task="text-classification",
        text="I love this.",
        options={"top_k": 1},
    )

    assert result[0]["label"] == "POSITIVE"
    assert created["task"] == "text-classification"

    history_file = tmp_path / "hf_pipeline_runs" / "history.jsonl"
    assert history_file.exists()

    lines = history_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["task"] == "text-classification"


def test_run_text_task_rejects_invalid_task(tmp_path: Path) -> None:
    sandbox = _StubSandbox(tmp_path)
    router = HFPipelineRouter(sandbox=sandbox, pipeline_factory=lambda *args, **kwargs: _FakePipeline())

    with pytest.raises(HFPipelineError, match="Unsupported pipeline task"):
        router.run_text_task(task="text-to-speech", text="hello")
