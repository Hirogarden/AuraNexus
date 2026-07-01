from pathlib import Path

import pytest

from core.security import SafeSandbox, SecurityInitializationError, SecurityViolationError


def test_sanitize_path_rejects_absolute_and_traversal(tmp_path: Path) -> None:
    sandbox = SafeSandbox(workspace_dir=tmp_path / "sandbox_workspace", require_isolation=False)

    with pytest.raises(SecurityViolationError):
        sandbox.sanitize_path("/etc/passwd")

    with pytest.raises(SecurityViolationError):
        sandbox.sanitize_path("../escape.txt")


def test_sanitize_path_rejects_symlink_escape(tmp_path: Path) -> None:
    sandbox_root = tmp_path / "sandbox_workspace"
    outside_root = tmp_path / "outside"
    outside_root.mkdir(parents=True, exist_ok=True)

    link_path = sandbox_root / "link"
    sandbox = SafeSandbox(workspace_dir=sandbox_root, require_isolation=False)

    try:
        link_path.symlink_to(outside_root, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"Symlink creation not permitted in this environment: {exc}")

    with pytest.raises(SecurityViolationError):
        sandbox.sanitize_path("link/secret.txt")


def test_fail_closed_when_bwrap_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from core import security as security_mod

    monkeypatch.setattr(security_mod.platform, "system", lambda: "Linux")
    monkeypatch.setattr(security_mod.shutil, "which", lambda _name: None)

    with pytest.raises(SecurityInitializationError):
        SafeSandbox(workspace_dir=tmp_path / "sandbox_workspace", require_isolation=True)


def test_non_linux_platforms_fail_closed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from core import security as security_mod

    monkeypatch.setattr(security_mod.platform, "system", lambda: "Windows")

    with pytest.raises(SecurityInitializationError):
        SafeSandbox(workspace_dir=tmp_path / "sandbox_workspace", require_isolation=True)


def test_execute_isolated_tool_blocks_host_handoff_binary(tmp_path: Path) -> None:
    sandbox = SafeSandbox(workspace_dir=tmp_path / "sandbox_workspace", require_isolation=False)

    with pytest.raises(SecurityViolationError, match="host hand-off binary"):
        sandbox.execute_isolated_tool(
            command=["xdg-open", "payload.txt"],
            timeout=1,
            allowed_binaries={"xdg-open"},
        )
