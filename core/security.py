import platform
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, Sequence, Iterable


class SecurityViolationError(Exception):
    """Raised when a tool or file transaction violates sandbox boundaries."""
    pass


class SecurityInitializationError(RuntimeError):
    """Raised when required isolation primitives are unavailable."""
    pass


class SafeSandbox:
    """
    Enforces path sanitation and fail-secure process isolation for AuraNexus.
    Ensures OpenClaw and Hugging Face tools operate within strict boundaries.
    """

    def __init__(
        self,
        workspace_dir: str | Path = "sandbox_workspace",
        allowed_binaries: Iterable[str] | None = None,
        require_isolation: bool = True,
    ):
        self.base_path = Path(workspace_dir).resolve()
        self.system = platform.system()
        self.require_isolation = require_isolation
        self.allowed_binaries = frozenset(allowed_binaries or ())
        self._ensure_workspace()
        if self.require_isolation:
            self._validate_isolation_primitives()

    def _ensure_workspace(self) -> None:
        """Create the isolated workspace directory securely if it doesn't exist."""
        try:
            self.base_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise SecurityViolationError(f"Failed to initialize secure storage workspace: {e}")

    def _validate_isolation_primitives(self) -> None:
        """Fail closed when native isolation primitives are missing or unsupported."""
        if self.system == "Linux":
            if shutil.which("bwrap") is None:
                raise SecurityInitializationError(
                    "Linux isolation requires bubblewrap (bwrap), but it is not installed."
                )
            return

        if self.system == "Windows":
            raise SecurityInitializationError(
                "Windows isolation is not yet implemented. Job Objects/AppContainer enforcement is required."
            )

        if self.system == "Darwin":
            raise SecurityInitializationError(
                "macOS isolation is not yet implemented. App Sandbox enforcement is required."
            )

        raise SecurityInitializationError(
            f"Unsupported platform for secure sandbox execution: {self.system}"
        )

    def sanitize_path(self, relative_path: str | Path) -> Path:
        """
        Forces path canonicalization. Prevents path traversal vulnerabilities (../)
        by validating that the resolved path stays entirely within the sandbox root.
        """
        try:
            raw_path = Path(relative_path)

            if raw_path.is_absolute():
                raise SecurityViolationError(
                    f"Access denied: absolute paths are forbidden ('{relative_path}')."
                )

            if any(part == ".." for part in raw_path.parts):
                raise SecurityViolationError(
                    f"Access denied: traversal operator detected in '{relative_path}'."
                )

            target_path = (self.base_path / raw_path).resolve(strict=False)
            try:
                target_path.relative_to(self.base_path)
            except ValueError as exc:
                raise SecurityViolationError(
                    f"Access denied: path escapes sandbox boundary ('{relative_path}')."
                ) from exc

            return target_path
        except SecurityViolationError:
            raise
        except Exception as e:
            raise SecurityViolationError(f"Path verification failure: {e}") from e

    def _validate_command(self, command: Sequence[str], allowed_binaries: Iterable[str] | None) -> None:
        if not command:
            raise SecurityViolationError("Execution blocked: empty command sequence.")

        if any(not isinstance(item, str) for item in command):
            raise SecurityViolationError("Execution blocked: command entries must all be strings.")

        binary = str(command[0]).strip()
        if not binary:
            raise SecurityViolationError("Execution blocked: empty executable name.")

        if "/" in binary or "\\" in binary:
            raise SecurityViolationError(
                "Execution blocked: executable must be a bare binary name, not a filesystem path."
            )

        blocked_host_handoff = {
            "xdg-open",
            "open",
            "start",
            "cmd",
            "powershell",
            "pwsh",
        }
        if binary.lower() in blocked_host_handoff:
            raise SecurityViolationError(
                f"Execution blocked: host hand-off binary '{binary}' is forbidden in sandbox mode."
            )

        allowlist = frozenset(allowed_binaries) if allowed_binaries is not None else self.allowed_binaries
        if not allowlist:
            raise SecurityViolationError(
                "Execution blocked: no binary allowlist configured for sandbox commands."
            )

        if binary not in allowlist:
            raise SecurityViolationError(
                f"Execution blocked: binary '{binary}' is not present in the allowlist."
            )

    def _build_linux_bwrap_prefix(self) -> list[str]:
        prefix = ["bwrap"]
        for ro_path in ("/usr", "/lib", "/lib64", "/bin"):
            if Path(ro_path).exists():
                prefix.extend(["--ro-bind", ro_path, ro_path])

        prefix.extend([
            "--proc", "/proc",
            "--dev", "/dev",
            "--tmpfs", "/tmp",
            "--bind", str(self.base_path), str(self.base_path),
            "--chdir", str(self.base_path),
            "--unshare-net",
            "--unshare-pid",
            "--die-with-parent",
            "--",
        ])
        return prefix

    def execute_isolated_tool(
        self,
        command: Sequence[str],
        timeout: int = 30,
        allowed_binaries: Iterable[str] | None = None,
    ) -> Dict[str, Any]:
        """
        Executes external tools (OpenClaw scripts, system commands) using localized
        isolation patterns. Bypasses leaky host desktop hand-offs completely.
        """
        self._validate_command(command, allowed_binaries)
        cmd_list = [str(arg) for arg in command]

        if self.system == "Linux":
            cmd_list = self._build_linux_bwrap_prefix() + cmd_list
        else:
            raise SecurityInitializationError(
                f"Tool execution denied: secure backend is not implemented for {self.system}."
            )

        try:
            # Force execution within the secure root directory context
            result = subprocess.run(
                cmd_list,
                cwd=self.base_path,
                capture_output=True,
                text=True,
                timeout=timeout,
                env={
                    "PATH": "/usr/bin:/bin",
                    "AURA_SANDBOX_ACTIVE": "1",
                    "AURA_SANDBOX_ROOT": str(self.base_path),
                }
            )
            
            return {
                "success": result.returncode == 0,
                "returncode": result.returncode,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
                "error": ""
            }
            
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "returncode": None,
                "stdout": "",
                "stderr": "",
                "error": f"Tool execution timed out after {timeout} seconds."
            }
        except Exception as e:
            return {
                "success": False,
                "returncode": None,
                "stdout": "",
                "stderr": "",
                "error": f"Execution engine failure: {e}"
            }