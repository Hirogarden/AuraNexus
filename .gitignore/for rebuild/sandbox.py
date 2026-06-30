"""Stage 2 security sandbox – opens links or files in an isolated environment.

Supported backends (selected automatically based on OS and availability):
* **firejail**  – Linux, uses Firejail process sandboxing
* **bubblewrap** – Linux, uses ``bwrap`` for namespace isolation

Usage::

    from daniel_suite.security.sandbox import Sandbox
    sb = Sandbox(backend="firejail")
    result = sb.open_url("https://example.com")
    result = sb.open_file("/tmp/document.pdf")
"""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Sequence


@dataclass
class SandboxResult:
    success: bool
    backend: str
    returncode: int | None = None
    stdout: str = ""
    stderr: str = ""
    error: str = ""


class SecurityInitializationError(RuntimeError):
    """Raised when required isolation primitives are unavailable."""


def _which(cmd: str) -> bool:
    """Return True if *cmd* is available on PATH."""
    return shutil.which(cmd) is not None


def _fatal_security_init(message: str, exc: Exception | None = None) -> None:
    """Crash-closed on any sandbox initialization failure."""
    details = f"{message}: {exc}" if exc is not None else message
    print(f"[security] FATAL sandbox initialization error: {details}", file=sys.stderr)
    raise SecurityInitializationError(details)


def _detect_backend(preferred: str) -> str:
    """Pick a supported backend.

    Fail-closed policy: only Linux namespace sandboxes are accepted.
    ``auto`` prefers firejail, then bubblewrap; if neither exists, startup fails.
    """
    system = platform.system()

    allowed = {"auto", "firejail", "bubblewrap"}
    if preferred not in allowed:
        _fatal_security_init(
            f"Unsupported sandbox backend {preferred!r}. "
            "Allowed values: auto, firejail, bubblewrap"
        )

    if system != "Linux":
        _fatal_security_init(
            f"Sandbox backend {preferred!r} requires Linux namespace isolation; host OS is {system}"
        )

    if preferred == "firejail":
        if _which("firejail"):
            return "firejail"
        _fatal_security_init("Configured sandbox backend firejail is not installed")

    if preferred == "bubblewrap":
        if _which("bwrap"):
            return "bubblewrap"
        _fatal_security_init("Configured sandbox backend bubblewrap is not installed")

    # preferred == auto: choose strongest available backend
    if _which("firejail"):
        return "firejail"
    if _which("bwrap"):
        return "bubblewrap"
    _fatal_security_init("No supported sandbox backend is available (missing firejail and bubblewrap)")
    return ""  # unreachable


class Sandbox:
    """Executes commands in an isolated sandbox environment."""

    def __init__(self, backend: str = "auto") -> None:
        self.backend = _detect_backend(backend)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def open_url(self, url: str) -> SandboxResult:
        """Open *url* inside the sandbox using the system browser."""
        if platform.system() == "Windows":
            cmd = ["cmd", "/c", "start", "", url]
        elif platform.system() == "Darwin":
            cmd = ["open", url]
        else:
            cmd = ["xdg-open", url]
        return self._run(cmd, label=f"open_url({url!r})")

    def open_file(self, path: str) -> SandboxResult:
        """Open *path* inside the sandbox."""
        if platform.system() == "Windows":
            cmd = ["cmd", "/c", "start", "", path]
        elif platform.system() == "Darwin":
            cmd = ["open", path]
        else:
            cmd = ["xdg-open", path]
        return self._run(cmd, label=f"open_file({path!r})")

    def run_command(self, command: Sequence[str]) -> SandboxResult:
        """Execute an arbitrary *command* sequence inside the sandbox."""
        return self._run(list(command), label=f"run_command({command!r})")

    def wrap_command(self, cmd: Sequence[str]) -> list[str]:
        """Return *cmd* prefixed with backend sandbox arguments.

        This is used for long-running worker subprocesses where the caller
        performs custom I/O and timeout handling instead of ``subprocess.run``.
        """
        raw = list(cmd)
        if self.backend == "firejail":
            return [
                "firejail",
                "--quiet",
                "--private",
                "--private-tmp",
                "--noroot",
                "--net=none",
                "--",
            ] + raw
        if self.backend == "bubblewrap":
            return [
                "bwrap",
                "--ro-bind", "/usr", "/usr",
                "--ro-bind", "/lib", "/lib",
                "--ro-bind", "/lib64", "/lib64",
                "--proc", "/proc",
                "--dev", "/dev",
                "--tmpfs", "/tmp",
                "--unshare-net",
                "--unshare-pid",
                "--die-with-parent",
                "--",
            ] + raw
        _fatal_security_init(f"Unsupported sandbox backend at runtime: {self.backend}")
        return []  # unreachable

    # ------------------------------------------------------------------
    # Backend implementations
    # ------------------------------------------------------------------

    def _run(self, cmd: list[str], label: str) -> SandboxResult:
        dispatch = {
            "firejail": self._run_firejail,
            "bubblewrap": self._run_bubblewrap,
        }
        runner = dispatch.get(self.backend)
        if runner is None:
            return SandboxResult(
                success=False,
                backend=self.backend,
                error=f"Unsupported sandbox backend: {self.backend}",
            )
        return runner(cmd, label)

    def _run_firejail(self, cmd: list[str], label: str) -> SandboxResult:
        """Run inside Firejail with a private /tmp, network disabled."""
        sandboxed = [
            "firejail",
            "--quiet",
            "--private",
            "--private-tmp",
            "--noroot",
            "--net=none",
            "--",
        ] + cmd
        return self._exec(sandboxed, label)

    def _run_bubblewrap(self, cmd: list[str], label: str) -> SandboxResult:
        """Run inside a bubblewrap (bwrap) namespace."""
        sandboxed = [
            "bwrap",
            "--ro-bind", "/usr", "/usr",
            "--ro-bind", "/lib", "/lib",
            "--ro-bind", "/lib64", "/lib64",
            "--proc", "/proc",
            "--dev", "/dev",
            "--tmpfs", "/tmp",
            "--unshare-net",
            "--unshare-pid",
            "--die-with-parent",
            "--",
        ] + cmd
        return self._exec(sandboxed, label)

    @staticmethod
    def _exec(
        cmd: list[str],
        label: str,
        env: dict[str, str] | None = None,
    ) -> SandboxResult:
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                env=env,
            )
            return SandboxResult(
                success=proc.returncode == 0,
                backend=cmd[0],
                returncode=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
            )
        except FileNotFoundError as exc:
            return SandboxResult(
                success=False,
                backend=cmd[0],
                error=f"Command not found: {exc}",
            )
        except subprocess.TimeoutExpired:
            return SandboxResult(
                success=False,
                backend=cmd[0],
                error=f"Sandbox execution timed out for: {label}",
            )
        except OSError as exc:
            return SandboxResult(
                success=False,
                backend=cmd[0],
                error=f"OS error during sandbox execution: {exc}",
            )
