"""
Parse TOOL_CALL blocks from LLM output.

Ported from AuraNexus.old/auranexus/actions/parser.py.

The LLM is instructed to emit tool calls in this format:

    [TOOL_CALL]
    action: web_search
    query: what is the latest news on AI
    [/TOOL_CALL]

parse_tool_calls() returns a list of (action, params) tuples.
strip_tool_calls() removes all TOOL_CALL blocks from a text string.
"""
from __future__ import annotations

import re
from typing import Dict, List, Tuple

_BLOCK_RE = re.compile(
    r"\[TOOL_CALL\](.*?)\[/TOOL_CALL\]",
    re.DOTALL | re.IGNORECASE,
)

_PARAM_RE = re.compile(r"^(\w+)\s*:\s*(.+)$", re.MULTILINE)


def parse_tool_calls(text: str) -> List[Tuple[str, Dict[str, str]]]:
    """
    Extract all TOOL_CALL blocks from *text*.

    Returns a list of (action, params) tuples where *params* is a dict of
    key→value strings (all keys lower-cased, "action" key removed).
    """
    results: List[Tuple[str, Dict[str, str]]] = []
    for m in _BLOCK_RE.finditer(text):
        inner = m.group(1)
        params: Dict[str, str] = {}
        for pm in _PARAM_RE.finditer(inner):
            key = pm.group(1).strip().lower()
            val = pm.group(2).strip()
            params[key] = val
        action = params.pop("action", "").lower()
        if action:
            results.append((action, params))
    return results


def strip_tool_calls(text: str) -> str:
    """Remove all TOOL_CALL blocks from *text*, leaving surrounding prose."""
    return _BLOCK_RE.sub("", text).strip()


TOOL_CALL_SYSTEM_HINT = """\
When you need to use a tool, emit a TOOL_CALL block in your response:

[TOOL_CALL]
action: <tool_name>
<param_name>: <value>
[/TOOL_CALL]

Available tools: web_search, read_file, list_directory, write_file, run_python.
Only use tools when they would genuinely help answer the user. Do not use tools for conversational replies."""
