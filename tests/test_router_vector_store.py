from pathlib import Path
from types import SimpleNamespace

from storage.vector_store import LocalVectorStore
from tools.router import ToolRegistry


class _StubSandbox:
    def __init__(self, root: Path):
        self.root = root
        self.last_sanitized = None

    def sanitize_path(self, relative_path: str):
        self.last_sanitized = relative_path
        return self.root / relative_path

    def execute_isolated_tool(self, command, timeout=30, allowed_binaries=None):
        return {
            "success": True,
            "command": list(command),
            "timeout": timeout,
            "allowed": sorted(allowed_binaries or []),
        }


def test_vector_store_uses_sandbox_path_resolver(tmp_path: Path) -> None:
    sandbox = _StubSandbox(tmp_path)
    store = LocalVectorStore(storage_path="vectors/index.json", sandbox=sandbox)

    assert sandbox.last_sanitized == "vectors/index.json"
    assert store.storage_path == tmp_path / "vectors/index.json"


def test_router_command_allowlist_enforced(tmp_path: Path) -> None:
    sandbox = _StubSandbox(tmp_path)
    router = ToolRegistry(sandbox=sandbox, allowed_commands={"python3"})

    blocked = router.execute_command(["bash", "-lc", "echo denied"], timeout=1)
    assert blocked["success"] is False

    allowed = router.execute_command(["python3", "-V"], timeout=2)
    assert allowed["success"] is True
    assert allowed["command"][0] == "python3"


def test_router_wires_openclaw_skills_as_first_class_tools(tmp_path: Path) -> None:
    sandbox = _StubSandbox(tmp_path)
    router = ToolRegistry(sandbox=sandbox, allowed_commands={"python3"})

    class _StubBridge:
        def __init__(self):
            self.calls = []

        def discover_skills(self):
            return {
                "echo_skill": SimpleNamespace(
                    description="Echo text",
                    parameters={"text": {"type": "string"}},
                    required=("text",),
                )
            }

        def execute_skill(self, name, arguments):
            self.calls.append((name, arguments))
            return {"name": name, "arguments": arguments}

    bridge = _StubBridge()
    count = router.register_openclaw_skills(bridge)
    assert count == 1

    result = router.execute_tool("echo_skill", {"text": "hello"})
    assert result["success"] is True
    assert result["result"]["name"] == "echo_skill"
    assert bridge.calls == [("echo_skill", {"text": "hello"})]


def test_router_wires_hf_pipeline_tool_as_first_class_tool(tmp_path: Path) -> None:
    sandbox = _StubSandbox(tmp_path)
    router = ToolRegistry(sandbox=sandbox)

    class _StubPipelineRouter:
        def __init__(self):
            self.calls = []

        def run_text_task(self, task, text, model=None, options=None):
            self.calls.append(
                {
                    "task": task,
                    "text": text,
                    "model": model,
                    "options": options,
                }
            )
            return [{"label": "OK", "score": 1.0}]

    pipeline_router = _StubPipelineRouter()
    tool_name = router.register_hf_pipeline_tool(pipeline_router, tool_name="hf_tool")
    assert tool_name == "hf_tool"

    result = router.execute_tool(
        "hf_tool",
        {
            "task": "text-classification",
            "text": "hello",
            "options": {"top_k": 1},
        },
    )
    assert result["success"] is True
    assert result["result"][0]["label"] == "OK"
    assert pipeline_router.calls[0]["task"] == "text-classification"
