from pathlib import Path

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
