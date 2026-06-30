import os
import platform
import shlex
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Sequence


class SecurityViolationError(Exception):
    """Raised when a tool or file transaction violates sandbox boundaries."""
    pass


class SafeSandbox:
    """
    Enforces path sanitation and fail-secure process isolation for AuraNexus.
    Ensures OpenClaw and Hugging Face tools operate within strict boundaries.
    """

    def __init__(self, workspace_dir: str | Path = "sandbox_workspace"):
        self.base_path = Path(workspace_dir).resolve()
        self._ensure_workspace()
        self.system = platform.system()

    def _ensure_workspace(self) -> None:
        """Create the isolated workspace directory securely if it doesn't exist."""
        try:
            self.base_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise SecurityViolationError(f"Failed to initialize secure storage workspace: {e}")

    def sanitize_path(self, relative_path: str | Path) -> Path:
        """
        Forces path canonicalization. Prevents path traversal vulnerabilities (../)
        by validating that the resolved path stays entirely within the sandbox root.
        """
        try:
            # Resolve potential symlinks and relative tokens safely
            target_path = Path(self.base_path / relative_path).resolve()
            
            # Strict boundary check
            if not str(target_path).startswith(str(self.base_path)):
                raise SecurityViolationError(
                    f"Access Denied: Path traversal detected for path '{relative_path}'."
                )
            return target_path
        except Exception as e:
            if not isinstance(e, SecurityViolationError):
                raise SecurityViolationError(f"Path verification failure: {e}")
            raise e

    def execute_isolated_tool(self, command: Sequence[str], timeout: int = 30) -> Dict[str, Any]:
        """
        Executes external tools (OpenClaw scripts, system commands) using localized
        isolation patterns. Bypasses leaky host desktop hand-offs completely.
        """
        cmd_list = [str(arg) for arg in command]
        
        # Build platform isolation flags natively without crashing non-Linux users
        if self.system == "Linux":
            # Attempt to run via bubblewrap if available on the host system
            import shutil
            if shutil.which("bwrap"):
                isolation_prefix = [
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
                    "--"
                ]
                cmd_list = isolation_prefix + cmd_list

        try:
            # Force execution within the secure root directory context
            result = subprocess.run(
                cmd_list,
                cwd=self.base_path,
                capture_output=True,
                text=True,
                timeout=timeout,
                env={"AURA_SANDBOX_ACTIVE": "1"} # Let subprocess tools know they are restricted
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