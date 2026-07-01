import json
from pathlib import Path
from types import SimpleNamespace

from storage.lorebook import LorebookManager
from storage.vector_store import LocalVectorStore
from storage.world_state import WorldState
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


def test_vector_store_builds_hirag_layers_and_multi_hop_retrieval(tmp_path: Path) -> None:
    sandbox = _StubSandbox(tmp_path)
    store = LocalVectorStore(
        storage_path="vectors/index.json",
        sandbox=sandbox,
        max_cluster_size=2,
        max_cluster_depth=4,
    )

    store.add_vector([0.98, 0.02, 0.0], "embers and ash", {"topic": "fire"})
    store.add_vector([0.95, 0.05, 0.0], "flame lore", {"topic": "fire"})
    store.add_vector([0.02, 0.97, 0.01], "tidal rites", {"topic": "water"})
    store.add_vector([0.01, 0.95, 0.04], "river scripture", {"topic": "water"})

    state = store.get_hirag_state()
    assert state["local_count"] == 4
    assert state["global_count"] >= 2
    assert state["bridge_count"] == 4

    results = store.query_hierarchical(query_vector=[1.0, 0.0, 0.0], top_k=2, top_clusters=1)
    assert len(results) == 2
    assert results[0][1]["topic"] == "fire"
    assert results[0][1]["hirag_cluster_id"] is not None


def test_vector_store_hirag_round_trip_persists_layers(tmp_path: Path) -> None:
    sandbox = _StubSandbox(tmp_path)
    store = LocalVectorStore(storage_path="vectors/index.json", sandbox=sandbox)
    store.add_vector([1.0, 0.0], "alpha", {"order": 1})
    store.add_vector([0.0, 1.0], "beta", {"order": 2})
    store.save_index()

    reloaded = LocalVectorStore(storage_path="vectors/index.json", sandbox=sandbox)
    state = reloaded.get_hirag_state()

    assert state["local_count"] == 2
    assert state["global_count"] >= 1
    assert state["bridge_count"] == 2

    query = reloaded.query_similarity([1.0, 0.0], top_k=1)
    assert query[0][0] == "alpha"
    assert query[0][1]["hirag_local_id"] >= 1


def test_vector_store_migrates_legacy_flat_index(tmp_path: Path) -> None:
    sandbox = _StubSandbox(tmp_path)
    legacy_path = tmp_path / "vectors" / "index.json"
    legacy_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_path.write_text(
        json.dumps(
            [
                {"vector": [1.0, 0.0], "text": "legacy fire", "metadata": {"topic": "fire"}},
                {"vector": [0.0, 1.0], "text": "legacy water", "metadata": {"topic": "water"}},
            ]
        ),
        encoding="utf-8",
    )

    store = LocalVectorStore(storage_path="vectors/index.json", sandbox=sandbox)
    state = store.get_hirag_state()

    assert state["local_count"] == 2
    assert state["bridge_count"] == 2
    hits = store.query_hierarchical([1.0, 0.0], top_k=1, top_clusters=1)
    assert hits[0][0] == "legacy fire"


def test_world_state_uses_sandbox_path_resolver(tmp_path: Path) -> None:
    sandbox = _StubSandbox(tmp_path)
    state = WorldState(data_path="state/world_state.json", sandbox=sandbox)

    assert sandbox.last_sanitized == "state/world_state.json"
    assert state.data_path == tmp_path / "state/world_state.json"


def test_lorebook_uses_sandbox_path_resolver(tmp_path: Path) -> None:
    sandbox = _StubSandbox(tmp_path)
    lorebook = LorebookManager(data_path="state/lorebook.json", sandbox=sandbox)

    assert sandbox.last_sanitized == "state/lorebook.json"
    assert lorebook.data_path == tmp_path / "state/lorebook.json"


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
