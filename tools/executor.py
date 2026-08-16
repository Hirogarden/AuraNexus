"""
Sandboxed tool executors for AuraNexus skills.

Ported and adapted from AuraNexus.old/auranexus/actions/executor.py.

Each executor takes a dict of params and returns a dict with:
  {"ok": bool, "output": str}

Path safety: all file operations are restricted to the user's home dir or /tmp.
Network: plain GET only, no cookies, 10s timeout.
Code execution: subprocess with 10s wall-clock timeout, stdout/stderr captured.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

from core.guardrails import is_sensitive_path, redact_sensitive_text

# ── Path safety ────────────────────────────────────────────────────────────────

def _safe_path(raw: str) -> Path | None:
    """Expand ~ and resolve the path.  Returns None if outside allowed roots."""
    try:
        p = Path(os.path.expanduser(raw)).resolve()
    except Exception:
        return None
    home = Path.home().resolve()
    tmp = Path("/tmp").resolve()
    if str(p).startswith(str(home)) or str(p).startswith(str(tmp)):
        if is_sensitive_path(p):
            return None
        return p
    return None


# ── Individual executors ───────────────────────────────────────────────────────

def exec_web_search(query: str) -> Dict[str, Any]:
    """Search the web via DuckDuckGo HTML lite (no API key required)."""
    query = str(query).strip()
    if not query:
        return {"ok": False, "output": "No query provided."}
    try:
        import requests as _req
        resp = _req.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers={"User-Agent": "AuraNexus/1.0 (private local assistant)"},
            timeout=10,
        )
        resp.raise_for_status()
        snippets = re.findall(
            r'class="result__snippet"[^>]*>(.*?)</a>',
            resp.text,
            re.DOTALL,
        )
        clean = [re.sub(r"<[^>]+>", "", s).strip() for s in snippets[:5]]
        clean = [c for c in clean if c]
        if not clean:
            return {"ok": True, "output": "Search returned no readable snippets."}
        output = f"Search results for: {query}\n\n" + "\n\n".join(
            f"{i + 1}. {s}" for i, s in enumerate(clean)
        )
        return {"ok": True, "output": redact_sensitive_text(output)}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "output": f"Search failed: {exc}"}


def exec_read_file(path: str) -> Dict[str, Any]:
    """Read a file inside the user's home directory (max 8,000 chars)."""
    raw = str(path).strip()
    if not raw:
        return {"ok": False, "output": "No path provided."}
    p = _safe_path(raw)
    if p is None:
        return {"ok": False, "output": f"Path not allowed (must be inside home or /tmp): {raw}"}
    if not p.exists():
        return {"ok": False, "output": f"File not found: {p}"}
    if not p.is_file():
        return {"ok": False, "output": f"Not a file: {p}"}
    try:
        MAX = 8_000
        content = p.read_text(errors="replace")
        truncated = len(content) > MAX
        if truncated:
            content = content[:MAX] + f"\n\n[… truncated at {MAX} chars]"
        return {"ok": True, "output": f"Contents of {p}:\n\n{redact_sensitive_text(content)}"}
    except OSError as exc:
        return {"ok": False, "output": f"Could not read file: {exc}"}


def exec_list_directory(path: str) -> Dict[str, Any]:
    """List a directory inside the user's home directory."""
    raw = str(path).strip()
    if not raw:
        return {"ok": False, "output": "No path provided."}
    p = _safe_path(raw)
    if p is None:
        return {"ok": False, "output": f"Path not allowed: {raw}"}
    if not p.exists():
        return {"ok": False, "output": f"Directory not found: {p}"}
    if not p.is_dir():
        return {"ok": False, "output": f"Not a directory: {p}"}
    try:
        entries = sorted(p.iterdir(), key=lambda e: (e.is_file(), e.name.lower()))
        lines = []
        for e in entries[:100]:
            if is_sensitive_path(e):
                continue
            tag = "/" if e.is_dir() else ""
            lines.append(f"  {e.name}{tag}")
        if len(list(p.iterdir())) > 100:
            lines.append("  … (truncated at 100 entries)")
        return {"ok": True, "output": f"Contents of {p}/:\n" + "\n".join(lines)}
    except OSError as exc:
        return {"ok": False, "output": f"Could not list directory: {exc}"}


def exec_write_file(path: str, content: str) -> Dict[str, Any]:
    """Write text to a file inside the user's home directory."""
    raw = str(path).strip()
    if not raw:
        return {"ok": False, "output": "No path provided."}
    p = _safe_path(raw)
    if p is None:
        return {"ok": False, "output": f"Path not allowed (must be inside home or /tmp): {raw}"}
    if p.is_dir():
        return {"ok": False, "output": f"Path is a directory: {p}"}
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(str(content), encoding="utf-8")
        return {"ok": True, "output": f"Written {len(content)} characters to {p}"}
    except OSError as exc:
        return {"ok": False, "output": f"Could not write file: {exc}"}


def exec_run_python(code: str) -> Dict[str, Any]:
    """Execute a Python snippet in a subprocess with a 10s timeout."""
    code = str(code).strip()
    if not code:
        return {"ok": False, "output": "No code provided."}
    try:
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=10,
            env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
        )
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += ("\n[stderr]\n" if result.stdout else "[stderr]\n") + result.stderr
        if not output:
            output = "(no output)"
        return {"ok": result.returncode == 0, "output": redact_sensitive_text(output.strip())}
    except subprocess.TimeoutExpired:
        return {"ok": False, "output": "Script timed out (10s limit)."}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "output": f"Execution error: {exc}"}


# ── Dispatch table ─────────────────────────────────────────────────────────────

SKILL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for current information or factual answers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query."}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a local file (restricted to home directory).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute or ~ path to the file."}
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List files and folders in a local directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute or ~ path to the directory."}
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write text content to a local file (restricted to home directory).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute or ~ path to write."},
                    "content": {"type": "string", "description": "Text content to write."},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_python",
            "description": "Execute a Python code snippet locally (10s timeout, stdout returned).",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Python code to execute."}
                },
                "required": ["code"],
            },
        },
    },
]


def dispatch(action: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Route an action name + params to the appropriate executor."""
    if action == "web_search":
        return exec_web_search(params.get("query", ""))
    if action == "read_file":
        return exec_read_file(params.get("path", ""))
    if action == "list_directory":
        return exec_list_directory(params.get("path", ""))
    if action == "write_file":
        return exec_write_file(params.get("path", ""), params.get("content", ""))
    if action == "run_python":
        return exec_run_python(params.get("code", ""))
    return {"ok": False, "output": f"Unknown action: {action}"}
