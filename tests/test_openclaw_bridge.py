import json
from pathlib import Path

import pytest

from tools.openclaw_bridge import OpenClawBridge, SkillRegistryError


class _StubSandbox:
    def __init__(self, root: Path):
        self.root = root
        self.last_command = None
        self.last_allowed = None

    def sanitize_path(self, relative_path: str):
        path = self.root / relative_path
        return path

    def execute_isolated_tool(self, command, timeout=30, allowed_binaries=None):
        self.last_command = list(command)
        self.last_allowed = tuple(allowed_binaries or ())
        return {
            "success": True,
            "returncode": 0,
            "stdout": "ok",
            "stderr": "",
            "error": "",
            "timeout": timeout,
        }


def test_discover_and_execute_skill(tmp_path: Path) -> None:
    sandbox = _StubSandbox(tmp_path)
    bridge = OpenClawBridge(sandbox=sandbox)

    schema = {
        "name": "echo_skill",
        "description": "Echo payload",
        "parameters": {
            "text": {"type": "string"},
        },
        "required": ["text"],
        "command": ["python3", "tools/echo_skill.py"],
        "timeout": 12,
    }

    bridge.register_skill_schema(schema)
    loaded = bridge.discover_skills()
    assert "echo_skill" in loaded

    result = bridge.execute_skill("echo_skill", {"text": "hello"})
    assert result["success"] is True
    assert sandbox.last_command[0] == "python3"
    assert sandbox.last_allowed == ("python3",)


def test_execute_skill_rejects_invalid_arguments(tmp_path: Path) -> None:
    sandbox = _StubSandbox(tmp_path)
    bridge = OpenClawBridge(sandbox=sandbox)

    bridge.register_skill_schema(
        {
            "name": "num_skill",
            "description": "Needs number",
            "parameters": {
                "value": {"type": "number"},
            },
            "required": ["value"],
            "command": ["python3", "tools/run_num_skill.py"],
        }
    )
    bridge.discover_skills()

    with pytest.raises(SkillRegistryError, match="missing required argument"):
        bridge.execute_skill("num_skill", {})

    with pytest.raises(SkillRegistryError, match="must be numeric"):
        bridge.execute_skill("num_skill", {"value": "oops"})


def test_register_skill_schema_rejects_absolute_or_traversal_command_tokens(tmp_path: Path) -> None:
    sandbox = _StubSandbox(tmp_path)
    bridge = OpenClawBridge(sandbox=sandbox)

    with pytest.raises(SkillRegistryError, match="absolute command paths"):
        bridge.register_skill_schema(
            {
                "name": "bad_abs",
                "description": "Invalid absolute path command token",
                "parameters": {"text": {"type": "string"}},
                "required": ["text"],
                "command": ["python3", "/tmp/run.py"],
            }
        )

    with pytest.raises(SkillRegistryError, match="traversal operator"):
        bridge.register_skill_schema(
            {
                "name": "bad_rel",
                "description": "Invalid traversal command token",
                "parameters": {"text": {"type": "string"}},
                "required": ["text"],
                "command": ["python3", "../outside.py"],
            }
        )
