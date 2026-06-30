"""
Action executors for ClawBot alternative actions.

Each function takes an ActionRequest and returns an ActionResult.
All execution is sandboxed as much as possible:
  - File ops:  paths validated, hard-confined to project_root/plugins
               and project_root/nexus_data (see _safe_path)
  - Web:       plain GET, no cookies, 10s timeout, text only
  - Scripts:   subprocess with 10s wall-clock timeout, stdout/stderr captured

Extensions
----------
Third-party ClawBot extensions are loaded as metadata only in the host
process; untrusted extension code is NEVER executed in-process.  Action
dispatch to extension handlers is performed in a dedicated worker subprocess.
"""
from __future__ import annotations

import ast
import json
import os
import platform
import re
import selectors
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from auranexus.actions.base import ActionRequest, ActionResult
from auranexus.engine.atomic_io import _atomic_write_text
from auranexus.actions.schema_registry import tool_schema_names

try:
    from security.sandbox import Sandbox, SecurityInitializationError
except Exception as exc:  # noqa: BLE001
    print(
        f"[security] FATAL executor initialization error: cannot import sandbox: {exc}",
        file=sys.stderr,
    )
    raise SystemExit(1) from exc


def _fatal_security_init(message: str) -> None:
    """Crash-closed helper for executor initialization/runtime preconditions."""
    print(f"[security] FATAL executor initialization error: {message}", file=sys.stderr)
    raise SecurityInitializationError(message)


_USE_POSIX_DIRFD_SAFETY = os.name == "posix" and all(
    hasattr(os, required) for required in ("O_NOFOLLOW", "O_DIRECTORY", "O_CLOEXEC")
)

if os.name == "posix" and not _USE_POSIX_DIRFD_SAFETY:
    _fatal_security_init(
        "Missing required os open(2) safety flags for TOCTOU-safe filesystem confinement"
    )
    raise SystemExit(1)


# ---------------------------------------------------------------------------
# Extension security: banned symbols
# ---------------------------------------------------------------------------

_EXT_BANNED_MODULES: frozenset[str] = frozenset({
    "subprocess", "pty", "signal", "resource", "posix", "nt",
    "socket", "ssl", "http", "urllib", "urllib3", "requests", "httpx",
    "ftplib", "smtplib",
    "shutil", "tempfile",
    "ctypes", "mmap", "winreg", "_winapi",
    "pickle", "shelve", "marshal",
    "threading", "multiprocessing", "concurrent",
    "inspect", "gc", "weakref",
    "py_compile", "compileall",
})

_EXT_BANNED_BUILTINS: frozenset[str] = frozenset({
    "exec", "eval", "compile", "__import__", "input",
    "breakpoint", "memoryview", "vars", "globals", "locals",
    # Block runtime introspection primitives used in string-concat
    # AST-bypass patterns (getattr(obj, 'cla'+'ss') etc.)
    "getattr", "setattr", "delattr", "type", "__build_class__",
})


class ExtensionError(Exception):
    """Raised when an extension fails the security scan or load."""


class SecurityError(RuntimeError):
    """Raised when a hard security limit is exceeded at runtime."""


_EXT_BANNED_DUNDERS: frozenset[str] = frozenset({
    "__class__", "__bases__", "__subclasses__", "__mro__",
    "__globals__", "__builtins__", "__code__", "__func__",
    "__self__", "__closure__", "__wrapped__", "__loader__",
    "__spec__", "__init__", "__new__", "__reduce__", "__reduce_ex__",
})

_MAX_WORKER_IO_BYTES = 10 * 1024 * 1024
_WORKER_IO_CHUNK = 65536
_SANDBOX_BACKEND = os.environ.get("AURANEXUS_TOOL_SANDBOX", "auto")


def _get_sandbox() -> Sandbox:
    """Create a sandbox instance or crash closed if unavailable."""
    try:
        return Sandbox(backend=_SANDBOX_BACKEND)
    except SecurityInitializationError as exc:
        print(f"[security] FATAL sandbox unavailable for tool execution: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


def _const_str(node: ast.AST) -> str | None:
    """Resolve static string expressions (including simple concatenation)."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _const_str(node.left)
        right = _const_str(node.right)
        if left is not None and right is not None:
            return left + right
    return None


def _run_subprocess_capped(
    cmd: list[str],
    timeout: float,
    env: dict[str, str],
    max_output_bytes: int = _MAX_WORKER_IO_BYTES,
) -> tuple[int, str, str]:
    """Run subprocess with hard stdout/stderr caps and robust decode fallback."""
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=False,
        env=env,
    )
    if proc.stdout is None or proc.stderr is None:
        raise OSError("Failed to open subprocess pipes")

    stdout_buf = bytearray()
    stderr_buf = bytearray()
    total = 0
    start = time.monotonic()

    if os.name == "posix":
        sel = selectors.DefaultSelector()
        os.set_blocking(proc.stdout.fileno(), False)
        os.set_blocking(proc.stderr.fileno(), False)
        sel.register(proc.stdout, selectors.EVENT_READ, data="stdout")
        sel.register(proc.stderr, selectors.EVENT_READ, data="stderr")

        try:
            while True:
                if time.monotonic() - start > timeout:
                    proc.kill()
                    try:
                        proc.wait(timeout=1)
                    except Exception:
                        pass
                    raise subprocess.TimeoutExpired(cmd=cmd, timeout=timeout)

                events = sel.select(timeout=0.1)
                for key, _ in events:
                    stream = key.fileobj
                    tag = key.data
                    try:
                        chunk = os.read(stream.fileno(), _WORKER_IO_CHUNK)
                    except BlockingIOError:
                        continue

                    if not chunk:
                        try:
                            sel.unregister(stream)
                        except Exception:
                            pass
                        continue

                    total += len(chunk)
                    if total > max_output_bytes:
                        proc.kill()
                        try:
                            proc.wait(timeout=1)
                        except Exception:
                            pass
                        raise SecurityError(
                            f"Worker output exceeded {max_output_bytes} bytes safety limit"
                        )

                    if tag == "stdout":
                        stdout_buf.extend(chunk)
                    else:
                        stderr_buf.extend(chunk)

                if proc.poll() is not None and not sel.get_map():
                    break
        finally:
            sel.close()
    else:
        lock = threading.Lock()
        cap_hit = threading.Event()

        def _drain(stream, target: bytearray) -> None:
            nonlocal total
            while True:
                chunk = stream.read(_WORKER_IO_CHUNK)
                if not chunk:
                    break
                with lock:
                    total += len(chunk)
                    if total > max_output_bytes:
                        cap_hit.set()
                target.extend(chunk)
                if cap_hit.is_set():
                    break

        out_thread = threading.Thread(target=_drain, args=(proc.stdout, stdout_buf), daemon=True)
        err_thread = threading.Thread(target=_drain, args=(proc.stderr, stderr_buf), daemon=True)
        out_thread.start()
        err_thread.start()

        while True:
            if cap_hit.is_set():
                proc.kill()
                try:
                    proc.wait(timeout=1)
                except Exception:
                    pass
                break
            if time.monotonic() - start > timeout:
                proc.kill()
                try:
                    proc.wait(timeout=1)
                except Exception:
                    pass
                raise subprocess.TimeoutExpired(cmd=cmd, timeout=timeout)
            if proc.poll() is not None:
                break
            time.sleep(0.02)

        out_thread.join(timeout=1)
        err_thread.join(timeout=1)

        if cap_hit.is_set():
            raise SecurityError(
                f"Worker output exceeded {max_output_bytes} bytes safety limit"
            )

    rc = proc.wait(timeout=1)
    out = stdout_buf.decode("utf-8", errors="replace")
    err = stderr_buf.decode("utf-8", errors="replace")
    return rc, out, err


def _ast_scan_extension(source: str, path: str) -> None:
    """Walk *source* AST; raise :exc:`ExtensionError` on any banned pattern."""
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as exc:
        raise ExtensionError(f"Syntax error in extension {path!r}: {exc}") from exc

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in _EXT_BANNED_MODULES:
                    raise ExtensionError(
                        f"Extension {path!r} imports banned module {alias.name!r}."
                    )
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root in _EXT_BANNED_MODULES:
                raise ExtensionError(
                    f"Extension {path!r} imports banned module {node.module!r}."
                )
        elif isinstance(node, ast.Call):
            func = node.func
            name: str | None = None
            if isinstance(func, ast.Name):
                name = func.id
            elif isinstance(func, ast.Attribute):
                name = func.attr
            if name in _EXT_BANNED_BUILTINS:
                raise ExtensionError(
                    f"Extension {path!r} calls banned function {name!r}."
                )
            # getattr(obj, '__globals__') etc.
            if name == "getattr" and len(node.args) >= 2:
                second = node.args[1]
                attr_name = _const_str(second)
                if attr_name in _EXT_BANNED_DUNDERS:
                    raise ExtensionError(
                        f"Extension {path!r} calls getattr() with banned "
                        f"dunder attribute {attr_name!r}."
                    )
        elif isinstance(node, ast.Attribute):
            if node.attr in _EXT_BANNED_DUNDERS:
                raise ExtensionError(
                    f"Extension {path!r} accesses banned dunder attribute "
                    f"{node.attr!r}; object-hierarchy traversal is not permitted."
                )
        elif isinstance(node, ast.Subscript):
            val = node.value
            if isinstance(val, ast.Name) and val.id == "__builtins__":
                raise ExtensionError(
                    f"Extension {path!r} accesses __builtins__ directly."
                )
        elif isinstance(node, ast.Name):
            if node.id == "__builtins__":
                raise ExtensionError(
                    f"Extension {path!r} references __builtins__ directly."
                )


# ---------------------------------------------------------------------------

# Project root is two levels up from this file (auranexus/actions/executor.py
# → auranexus/ → project root).
_PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent.parent

# Hard-coded allowlist: only these subdirectories of the project root may be
# read from or written to.  No home-directory-wide or /tmp access.
_ALLOWED_ROOTS: tuple[Path, ...] = (
    (_PROJECT_ROOT / "plugins").resolve(),
    (_PROJECT_ROOT / "nexus_data").resolve(),
)


def _safe_path(raw: str) -> Path:
    """Canonicalise *raw* and enforce containment under allowed roots."""
    if not raw or not raw.strip():
        raise ValueError("Empty path is not allowed.")

    try:
        resolved = Path(os.path.expanduser(raw)).resolve()
    except Exception as exc:
        raise PermissionError(f"Cannot resolve path {raw!r}: {exc}") from exc

    if not any(resolved.is_relative_to(allowed) for allowed in _ALLOWED_ROOTS):
        roots_display = ", ".join(str(r) for r in _ALLOWED_ROOTS)
        raise PermissionError(
            f"Path {resolved!r} is outside the allowed directories "
            f"({roots_display}). Access denied."
        )

    return resolved


def _allowed_root_for(path: Path) -> Path:
    for root in _ALLOWED_ROOTS:
        if path.is_relative_to(root):
            return root
    raise PermissionError(f"Path {path!r} is outside allowed roots.")


def _relative_parts(root: Path, path: Path) -> list[str]:
    rel = path.relative_to(root)
    return [p for p in rel.parts if p not in ("", ".")]


def _open_root_fd(root: Path) -> int:
    if not _USE_POSIX_DIRFD_SAFETY:
        raise PermissionError("POSIX dirfd safety mode unavailable on this platform")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC
    return os.open(str(root), flags)


def _mkdirs_under_root(root: Path, relative_dir: Path) -> None:
    """Create directories under *root* using dir-fd operations with O_NOFOLLOW."""
    if not _USE_POSIX_DIRFD_SAFETY:
        (root / relative_dir).mkdir(parents=True, exist_ok=True)
        return
    parts = [p for p in relative_dir.parts if p not in ("", ".")]
    root_fd = _open_root_fd(root)
    current_fd = root_fd
    opened: list[int] = []
    try:
        for part in parts:
            try:
                next_fd = os.open(
                    part,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                    dir_fd=current_fd,
                )
            except FileNotFoundError:
                os.mkdir(part, mode=0o700, dir_fd=current_fd)
                next_fd = os.open(
                    part,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                    dir_fd=current_fd,
                )
            opened.append(next_fd)
            current_fd = next_fd
    finally:
        for fd in reversed(opened):
            try:
                os.close(fd)
            except OSError:
                pass
        try:
            os.close(root_fd)
        except OSError:
            pass


def _open_under_root(root: Path, path: Path, flags: int, mode: int = 0o600) -> int:
    """Open *path* beneath *root* with O_NOFOLLOW on each traversed component."""
    if not _USE_POSIX_DIRFD_SAFETY:
        return os.open(str(path), flags, mode)
    parts = _relative_parts(root, path)
    if not parts:
        raise PermissionError("Direct access to root directory path is not allowed.")

    root_fd = _open_root_fd(root)
    current_fd = root_fd
    opened: list[int] = []
    try:
        for part in parts[:-1]:
            next_fd = os.open(
                part,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=current_fd,
            )
            opened.append(next_fd)
            current_fd = next_fd

        final_flags = flags | os.O_NOFOLLOW | os.O_CLOEXEC
        if flags & os.O_CREAT:
            fd = os.open(parts[-1], final_flags, mode, dir_fd=current_fd)
        else:
            fd = os.open(parts[-1], final_flags, dir_fd=current_fd)
        return fd
    finally:
        for dfd in reversed(opened):
            try:
                os.close(dfd)
            except OSError:
                pass
        try:
            os.close(root_fd)
        except OSError:
            pass


def _safe_read_text(path: Path) -> str:
    if not _USE_POSIX_DIRFD_SAFETY:
        return path.read_text(encoding="utf-8", errors="replace")
    root = _allowed_root_for(path)
    fd = _open_under_root(root, path, os.O_RDONLY)
    try:
        with os.fdopen(fd, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        raise


def _safe_write_text(path: Path, content: str) -> None:
    root = _allowed_root_for(path)
    rel_parent = path.parent.relative_to(root)
    _mkdirs_under_root(root, rel_parent)
    _atomic_write_text(path, content)


def _safe_list_dir(path: Path) -> list[Path]:
    if not _USE_POSIX_DIRFD_SAFETY:
        return [path / name for name in os.listdir(path)]
    root = _allowed_root_for(path)
    fd = _open_under_root(root, path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        entries = os.listdir(fd)
    finally:
        try:
            os.close(fd)
        except OSError:
            pass
    return [path / name for name in entries]


# ---------------------------------------------------------------------------
# Individual executors
# ---------------------------------------------------------------------------

def _exec_web_search(req: ActionRequest) -> ActionResult:
    query = req.params.get("query", "").strip()
    if not query:
        return ActionResult(action=req.action, ok=False, output="No query provided.")

    try:
        import requests as _req
        # DuckDuckGo HTML lite — no API key, no tracking, plain text friendly
        resp = _req.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers={"User-Agent": "AuraNexus/1.0 (private local assistant)"},
            timeout=10,
        )
        resp.raise_for_status()
        # Very lightweight parse: grab result snippets without pulling in bs4
        import re
        snippets = re.findall(
            r'class="result__snippet"[^>]*>(.*?)</a>',
            resp.text,
            re.DOTALL,
        )
        # Strip HTML tags
        clean = [re.sub(r"<[^>]+>", "", s).strip() for s in snippets[:5]]
        clean = [c for c in clean if c]
        if not clean:
            return ActionResult(
                action=req.action, ok=True,
                output="Search returned no readable snippets.",
            )
        output = f"Search results for: {query}\n\n" + "\n\n".join(
            f"{i+1}. {s}" for i, s in enumerate(clean)
        )
        return ActionResult(action=req.action, ok=True, output=output)

    except Exception as exc:  # noqa: BLE001
        return ActionResult(action=req.action, ok=False, output=f"Search failed: {exc}")


def _exec_read_file(req: ActionRequest) -> ActionResult:
    raw = req.params.get("path", "").strip()
    if not raw:
        return ActionResult(action=req.action, ok=False, output="No path provided.")

    try:
        p = _safe_path(raw)
    except (PermissionError, ValueError) as exc:
        return ActionResult(action=req.action, ok=False, output=f"Path not allowed: {exc}")

    try:
        MAX = 8_000  # chars
        content = _safe_read_text(p)
        truncated = len(content) > MAX
        if truncated:
            content = content[:MAX] + f"\n\n[… file truncated at {MAX} characters]"
        return ActionResult(
            action=req.action, ok=True,
            output=f"Contents of {p}:\n\n{content}",
        )
    except FileNotFoundError:
        return ActionResult(action=req.action, ok=False, output=f"File not found: {p}")
    except IsADirectoryError:
        return ActionResult(action=req.action, ok=False, output=f"Not a file: {p}")
    except OSError as exc:
        return ActionResult(action=req.action, ok=False, output=f"Could not read file: {exc}")


def _exec_list_directory(req: ActionRequest) -> ActionResult:
    raw = req.params.get("path", "").strip()
    if not raw:
        return ActionResult(action=req.action, ok=False, output="No path provided.")

    try:
        p = _safe_path(raw)
    except (PermissionError, ValueError) as exc:
        return ActionResult(action=req.action, ok=False, output=f"Path not allowed: {exc}")

    try:
        entries = sorted(_safe_list_dir(p), key=lambda e: (e.is_file(), e.name.lower()))
        lines = []
        for e in entries[:100]:
            tag = "/" if e.is_dir() else ""
            lines.append(f"  {e.name}{tag}")
        if len(entries) > 100:
            lines.append("  … (truncated at 100 entries)")
        return ActionResult(
            action=req.action, ok=True,
            output=f"Contents of {p}/:\n" + "\n".join(lines),
        )
    except FileNotFoundError:
        return ActionResult(action=req.action, ok=False, output=f"Directory not found: {p}")
    except NotADirectoryError:
        return ActionResult(action=req.action, ok=False, output=f"Not a directory: {p}")
    except OSError as exc:
        return ActionResult(action=req.action, ok=False, output=f"Could not list directory: {exc}")


def _exec_run_python(req: ActionRequest) -> ActionResult:
    code = req.params.get("code", "").strip()
    if not code:
        return ActionResult(action=req.action, ok=False, output="No code provided.")

    # Stage 1 — code signature scan (local DB, no network).
    # This is a last-resort check; primary scanning happens before the
    # confirmation dialog in _handle_tool_call.  Any BLOCKED verdict here
    # means the scan was bypassed somehow — refuse unconditionally.
    try:
        from security.scanner import ContentScanner, Verdict
        scan = ContentScanner().scan_code(code)
        if scan.verdict == Verdict.BLOCKED:
            reasons_text = "\n".join(f"  • {r}" for r in scan.reasons)
            return ActionResult(
                action=req.action, ok=False,
                output=f"Execution refused — code matched blocked patterns:\n{reasons_text}",
            )
    except ImportError:
        pass  # security module optional

    try:
        sb = _get_sandbox()
        result = sb.run_command([sys.executable, "-I", "-c", code])
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += ("\n[stderr]\n" if result.stdout else "[stderr]\n") + result.stderr
        if not output:
            output = "(no output)"
        return ActionResult(action=req.action, ok=result.success, output=output.strip())

    except SecurityInitializationError as exc:
        print(f"[security] FATAL sandbox unavailable for run_python: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    except Exception as exc:  # noqa: BLE001
        return ActionResult(action=req.action, ok=False, output=f"Execution error: {exc}")


def _exec_write_file(req: ActionRequest) -> ActionResult:
    raw     = req.params.get("path", "").strip()
    content = req.params.get("content", "")
    if not raw:
        return ActionResult(action=req.action, ok=False, output="No path provided.")

    try:
        p = _safe_path(raw)
    except (PermissionError, ValueError) as exc:
        return ActionResult(action=req.action, ok=False, output=f"Path not allowed: {exc}")

    try:
        _safe_write_text(p, content)
        return ActionResult(
            action=req.action, ok=True,
            output=f"Written {len(content)} characters to {p}",
        )
    except IsADirectoryError:
        return ActionResult(action=req.action, ok=False, output=f"Path is a directory: {p}")
    except OSError as exc:
        return ActionResult(action=req.action, ok=False, output=f"Could not write file: {exc}")


def _exec_open_path(req: ActionRequest) -> ActionResult:
    """Open a file, folder, or URL with the system default application (xdg-open)."""
    raw = req.params.get("path", "").strip()
    if not raw:
        return ActionResult(action=req.action, ok=False, output="No path provided.")

    # Allow http/https URLs directly — xdg-open handles them fine
    if raw.startswith(("http://", "https://")):
        target = raw
    else:
        try:
            p = _safe_path(raw)
        except (PermissionError, ValueError) as exc:
            return ActionResult(action=req.action, ok=False, output=f"Path not allowed: {exc}")
        if not p.exists():
            return ActionResult(action=req.action, ok=False, output=f"Path not found: {p}")
        target = str(p)

    try:
        sb = _get_sandbox()
        system = platform.system()
        if system == "Windows":
            launch_cmd = ["cmd", "/c", "start", "", target]
        elif system == "Darwin":
            launch_cmd = ["open", target]
        else:
            launch_cmd = ["xdg-open", target]

        result = sb.run_command(launch_cmd)
        if result.success:
            return ActionResult(action=req.action, ok=True, output=f"Opened: {target}")
        err = result.error or result.stderr or "sandbox launch failed"
        return ActionResult(action=req.action, ok=False, output=f"Could not open: {err}")
    except FileNotFoundError:
        return ActionResult(
            action=req.action, ok=False,
            output="xdg-open not found. Cannot open files on this system.",
        )
    except Exception as exc:  # noqa: BLE001
        return ActionResult(action=req.action, ok=False, output=f"Could not open: {exc}")


# Safe app-name pattern: letters, digits, hyphens, dots, underscores only.
# No shell metacharacters, no path separators, no spaces.
_APP_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-\.]{0,63}$")


def _exec_launch_app(req: ActionRequest) -> ActionResult:
    """Launch an installed application by name (e.g. 'firefox', 'nautilus')."""
    app = req.params.get("app", "").strip()
    if not app:
        return ActionResult(action=req.action, ok=False, output="No application name provided.")

    if not _APP_NAME_RE.match(app):
        return ActionResult(
            action=req.action, ok=False,
            output=(
                f"'{app}' is not a valid application name. "
                "Provide a simple name like 'firefox' or 'gedit' — no spaces or special characters."
            ),
        )

    try:
        sb = _get_sandbox()
        result = sb.run_command([app])
        if result.success:
            return ActionResult(action=req.action, ok=True, output=f"Launched: {app}")
        err = result.error or result.stderr or "sandbox launch failed"
        return ActionResult(action=req.action, ok=False, output=f"Could not launch '{app}': {err}")
    except FileNotFoundError:
        return ActionResult(
            action=req.action, ok=False,
            output=f"Application not found: '{app}'. Make sure it's installed and on your PATH.",
        )
    except Exception as exc:  # noqa: BLE001
        return ActionResult(action=req.action, ok=False, output=f"Could not launch '{app}': {exc}")


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_EXECUTORS = {
    "web_search":     _exec_web_search,
    "read_file":      _exec_read_file,
    "list_directory": _exec_list_directory,
    "run_python":     _exec_run_python,
    "write_file":     _exec_write_file,
    "open_path":      _exec_open_path,
    "launch_app":     _exec_launch_app,
}

_SCHEMA_TOOL_NAMES = tool_schema_names()
_EXECUTOR_TOOL_NAMES = set(_EXECUTORS.keys())
if _SCHEMA_TOOL_NAMES != _EXECUTOR_TOOL_NAMES:
    _missing_exec = sorted(_SCHEMA_TOOL_NAMES - _EXECUTOR_TOOL_NAMES)
    _missing_schema = sorted(_EXECUTOR_TOOL_NAMES - _SCHEMA_TOOL_NAMES)
    _fatal_security_init(
        "Tool schema/executor mismatch detected. "
        f"Missing executors: {_missing_exec or 'none'}; "
        f"Missing schemas: {_missing_schema or 'none'}"
    )

# ---------------------------------------------------------------------------
# Extension management
# ---------------------------------------------------------------------------

# path -> registered action names
_EXTENSION_REGISTRY: dict[str, set[str]] = {}

# action_name -> extension path that owns the action
_EXTENSION_ACTION_PATHS: dict[str, str] = {}


def _restricted_subprocess_env() -> dict[str, str]:
    tmp = tempfile.gettempdir()
    return {
        "PATH": os.environ.get("PATH", ""),
        "HOME": tmp,
        "TMPDIR": tmp,
        "TEMP": tmp,
        "PYTHONNOUSERSITE": "1",
        "PYTHONUNBUFFERED": "1",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
    }


def _extract_executor_action_names(source: str, path: str) -> set[str]:
    """Parse extension source and return EXECUTORS dict keys without executing code."""
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as exc:
        raise ExtensionError(f"Syntax error in extension {path!r}: {exc}") from exc

    action_names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue

        value_node = node.value if isinstance(node, ast.Assign) else node.value
        if value_node is None or not isinstance(value_node, ast.Dict):
            continue

        targets: list[ast.expr] = node.targets if isinstance(node, ast.Assign) else [node.target]
        if not any(isinstance(t, ast.Name) and t.id == "EXECUTORS" for t in targets):
            continue

        for key_node in value_node.keys:
            if isinstance(key_node, ast.Constant) and isinstance(key_node.value, str):
                action_names.add(key_node.value.strip())
        break

    return {a for a in action_names if a}


def _run_extension_action(path: str, req: ActionRequest) -> ActionResult:
    """Execute extension action in a dedicated subprocess (never in-process)."""
    payload = json.dumps({"action": req.action, "params": req.params, "raw": req.raw})
    cmd = [
        sys.executable,
        "-I",
        "-m",
        "auranexus.actions.extension_worker",
        "--path",
        path,
        "--action",
        req.action,
        "--request",
        payload,
    ]

    try:
        sandbox = Sandbox(backend=os.environ.get("AURANEXUS_WORKER_SANDBOX", "auto"))
        cmd = sandbox.wrap_command(cmd)
    except SecurityInitializationError as exc:
        return ActionResult(
            action=req.action,
            ok=False,
            output=f"Worker sandbox unavailable: {exc}",
        )

    try:
        returncode, stdout_text, stderr_text = _run_subprocess_capped(
            cmd,
            timeout=10,
            env=_restricted_subprocess_env(),
        )
    except subprocess.TimeoutExpired:
        return ActionResult(
            action=req.action,
            ok=False,
            output=f"Extension action timed out after 10s: {req.action}",
        )
    except OSError as exc:
        return ActionResult(
            action=req.action,
            ok=False,
            output=f"Extension worker launch failed: {exc}",
        )
    except SecurityError as exc:
        return ActionResult(
            action=req.action,
            ok=False,
            output=f"Extension worker blocked by security limit: {exc}",
            denied=True,
        )

    if returncode != 0:
        err = stderr_text.strip() or stdout_text.strip() or "unknown error"
        return ActionResult(
            action=req.action,
            ok=False,
            output=f"Extension worker failed for {req.action}: {err}",
        )

    try:
        data = json.loads(stdout_text)
        return ActionResult(
            action=req.action,
            ok=bool(data.get("ok", False)),
            output=str(data.get("output", "")),
            denied=bool(data.get("denied", False)),
        )
    except Exception as exc:  # noqa: BLE001
        return ActionResult(
            action=req.action,
            ok=False,
            output=f"Invalid extension worker response: {exc}",
        )


def load_extension(path: str) -> str | None:
    """Load a ClawBot extension from *path*.

    The file must expose an ``EXECUTORS`` dict mapping action-name strings to
    callables.  Built-in action names cannot be overridden.

        Security gates applied before registration:
      1. Path must be inside project_root/plugins (NOT nexus_data — data and
         executable code must be strictly isolated).
      2. AST pre-scan rejects banned imports and builtins.
            3. Action names are extracted from EXECUTORS dict using AST only.

        Extension code is NEVER imported/executed in-process.  Handlers are run
        in a dedicated worker subprocess at dispatch time.

    Returns an error string on failure, or ``None`` on success.
    """
    # ── Gate 1: path must be inside plugins/ only ─────────────────────
    # _safe_path() allows both plugins/ and nexus_data/; extensions must
    # only come from plugins/ so code and data are strictly separated.
    try:
        safe = _safe_path(path)
    except (PermissionError, ValueError) as exc:
        return f"Extension path not allowed: {exc}"

    _plugins_root = (_PROJECT_ROOT / "plugins").resolve()
    if not safe.is_relative_to(_plugins_root):
        return (
            f"Extension path not allowed: extensions must reside inside "
            f"{_plugins_root} (code and data directories are isolated). "
            f"Got: {safe}"
        )

    abs_path = str(safe)

    if abs_path in _EXTENSION_REGISTRY:
        return None  # already loaded

    stem = safe.stem

    # ── Gate 2: AST pre-scan ──────────────────────────────────────────
    try:
        source = safe.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return f"Cannot read extension {path!r}: {exc}"

    try:
        _ast_scan_extension(source, abs_path)
    except ExtensionError as exc:
        return f"Extension security scan blocked {stem!r}: {exc}"

    try:
        ext_actions = _extract_executor_action_names(source, abs_path)
    except ExtensionError as exc:
        return f"Extension {stem!r} blocked at registration: {exc}"

    if not ext_actions:
        return (
            f"Extension {stem} has no EXECUTORS dict or it is empty. "
            "Make sure the file defines EXECUTORS = {'action_name': handler_fn, ...}."
        )

    added: set[str] = set()
    already_extended = _already_extended_actions()
    for action_name in ext_actions:
        if action_name in _EXECUTORS and action_name not in already_extended:
            # Do not silently override built-ins
            continue
        _EXTENSION_ACTION_PATHS[action_name] = abs_path
        added.add(action_name)

    if not added:
        return (
            f"Extension {stem}: no new actions were registered "
            "(all names conflict with built-in actions)."
        )

    _EXTENSION_REGISTRY[abs_path] = added
    return None


def _already_extended_actions() -> set[str]:
    """Return the set of all action names registered by any extension."""
    result: set[str] = set()
    for _, actions in _EXTENSION_REGISTRY.items():
        result |= actions
    return result


def unload_extension(path: str) -> None:
    """Remove an extension and its registered actions."""
    abs_path = str(Path(path).resolve())
    actions = _EXTENSION_REGISTRY.pop(abs_path, None)
    if actions is None:
        return
    for action_name in actions:
        _EXTENSION_ACTION_PATHS.pop(action_name, None)


def sync_extensions(paths: list[str]) -> dict[str, str]:
    """Synchronise loaded extensions to exactly *paths*.

    Returns a dict of ``{path: error_message}`` for any paths that failed.
    """
    desired = {str(Path(p).resolve()) for p in paths}
    current = set(_EXTENSION_REGISTRY.keys())

    for p in list(current - desired):
        unload_extension(p)

    errors: dict[str, str] = {}
    for p in paths:
        abs_p = str(Path(p).resolve())
        if abs_p not in _EXTENSION_REGISTRY:
            err = load_extension(p)
            if err:
                errors[p] = err
    return errors


def loaded_extension_paths() -> list[str]:
    """Return the list of currently loaded extension file paths."""
    return list(_EXTENSION_REGISTRY.keys())


def execute(req: ActionRequest) -> ActionResult:
    """Run the action.  Should only be called after user confirmation."""
    ext_path = _EXTENSION_ACTION_PATHS.get(req.action)
    if ext_path is not None:
        return _run_extension_action(ext_path, req)

    handler = _EXECUTORS.get(req.action)
    if handler is None:
        return ActionResult(
            action=req.action, ok=False,
            output=f"Unknown action '{req.action}'.",
        )
    return handler(req)
