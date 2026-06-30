"""Schema-driven tool registry and prompt formatter for AuraNexus.

This module provides a single source of truth for tool capabilities so the
model receives an explicit schema rather than prose-only descriptions.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from auranexus.actions.assistant_profiles import format_profile_block
from auranexus.actions.mcp_bridge import format_mcp_prompt_block


@dataclass(frozen=True)
class ToolSchema:
    name: str
    description: str
    risk: str
    parameters: dict[str, dict[str, Any]]
    required: tuple[str, ...]


TOOL_SCHEMAS: dict[str, ToolSchema] = {
    "web_search": ToolSchema(
        name="web_search",
        description="Search public web snippets for a query.",
        risk="medium",
        parameters={
            "query": {"type": "string", "min_length": 1, "max_length": 512},
        },
        required=("query",),
    ),
    "read_file": ToolSchema(
        name="read_file",
        description="Read text file contents from allowed local directories.",
        risk="low",
        parameters={
            "path": {"type": "string", "min_length": 1, "max_length": 4096},
        },
        required=("path",),
    ),
    "list_directory": ToolSchema(
        name="list_directory",
        description="List files/folders in an allowed local directory.",
        risk="low",
        parameters={
            "path": {"type": "string", "min_length": 1, "max_length": 4096},
        },
        required=("path",),
    ),
    "run_python": ToolSchema(
        name="run_python",
        description="Run short Python snippets in the isolated sandbox.",
        risk="high",
        parameters={
            "code": {"type": "string", "min_length": 1, "max_length": 12000},
        },
        required=("code",),
    ),
    "write_file": ToolSchema(
        name="write_file",
        description="Write text to an allowed local file path.",
        risk="high",
        parameters={
            "path": {"type": "string", "min_length": 1, "max_length": 4096},
            "content": {"type": "string", "min_length": 0, "max_length": 500000},
        },
        required=("path", "content"),
    ),
    "open_path": ToolSchema(
        name="open_path",
        description="Open a URL or local path in sandbox-isolated launcher.",
        risk="medium",
        parameters={
            "path": {"type": "string", "min_length": 1, "max_length": 4096},
        },
        required=("path",),
    ),
    "launch_app": ToolSchema(
        name="launch_app",
        description="Launch a local application by executable name.",
        risk="medium",
        parameters={
            "app": {"type": "string", "min_length": 1, "max_length": 128},
        },
        required=("app",),
    ),
}


def tool_schema_names() -> set[str]:
    """Return the set of registered built-in tool schema names."""
    return set(TOOL_SCHEMAS.keys())


def format_system_tool_prompt() -> str:
    """Render deterministic system instructions containing all tool schemas."""
    lines: list[str] = []
    lines.append("You may call tools only when the user explicitly requests an action.")
    lines.append("Use exactly one tool call block at a time in this format:")
    lines.append("[TOOL_CALL]")
    lines.append("action: <tool_name>")
    lines.append("<param_name>: <value>")
    lines.append("[/TOOL_CALL]")
    lines.append("")
    lines.append(format_profile_block())
    lines.append("")
    lines.append("Tool schemas:")
    for schema in TOOL_SCHEMAS.values():
        lines.append(f"- {schema.name} (risk: {schema.risk})")
        lines.append(f"  description: {schema.description}")
        lines.append(f"  tool_card: use {schema.name} only when its declared capability exactly matches the user's requested action")
        req = ", ".join(schema.required) if schema.required else "none"
        lines.append(f"  required: {req}")
        for pname, spec in schema.parameters.items():
            ptype = str(spec.get("type", "string"))
            min_len = spec.get("min_length")
            max_len = spec.get("max_length")
            bounds = []
            if min_len is not None:
                bounds.append(f"min={min_len}")
            if max_len is not None:
                bounds.append(f"max={max_len}")
            btxt = f" ({', '.join(bounds)})" if bounds else ""
            lines.append(f"  - {pname}: {ptype}{btxt}")
    lines.append("")
    lines.append("Rules:")
    lines.append("- Never emit multiple TOOL_CALL blocks in one response.")
    lines.append("- Do not invent parameters not listed in the schema.")
    lines.append("- If needed parameters are missing, ask a clarifying question instead of calling a tool.")
    mcp_block = format_mcp_prompt_block()
    if mcp_block:
        lines.append("")
        lines.append(mcp_block)
    return "\n".join(lines).strip()


def validate_action_params(action: str, params: dict[str, str]) -> tuple[bool, str]:
    """Validate params against schema before execution."""
    schema = TOOL_SCHEMAS.get(action)
    if schema is None:
        return False, f"Unknown action: {action}"

    for key in schema.required:
        if key not in params:
            return False, f"Missing required parameter: {key}"

    allowed = set(schema.parameters.keys())
    for key in params:
        if key not in allowed:
            return False, f"Unexpected parameter: {key}"

    for key, value in params.items():
        spec = schema.parameters[key]
        if not isinstance(value, str):
            return False, f"Parameter {key} must be string"
        min_len = int(spec.get("min_length", 0))
        max_len = int(spec.get("max_length", 10_000_000))
        if len(value) < min_len:
            return False, f"Parameter {key} shorter than minimum {min_len}"
        if len(value) > max_len:
            return False, f"Parameter {key} longer than maximum {max_len}"

    return True, ""
