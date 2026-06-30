"""Two-stage security gate: Stage 1 (scan) → Stage 2 (sandbox).

Usage::

    from .gate import SecurityGate, GateResult
    gate = SecurityGate(cfg)
    result = gate.open_url("https://example.com")
    if result.allowed:
        print("Opened safely")
    else:
        print("Blocked:", result.reason)
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Any

from .sandbox import Sandbox, SandboxResult, SecurityInitializationError
from .scanner import ContentScanner, ScanResult, Verdict


@dataclass
class GateResult:
    allowed: bool
    stage1: ScanResult | None = None
    stage2: SandboxResult | None = None
    reason: str = ""
    warnings: list[str] = field(default_factory=list)


class SecurityGate:
    """Orchestrates the two-stage security check for any link, file, or command.

    Stage 1 – :class:`~daniel_suite.security.scanner.ContentScanner`:
        Static analysis of the content/URL for known risk signals.
        If the verdict is ``BLOCKED`` the item is rejected immediately.
        If the verdict is ``SUSPICIOUS`` a warning is surfaced to the user
        but execution continues to Stage 2.

    Stage 2 – :class:`~daniel_suite.security.sandbox.Sandbox`:
        The item is opened/executed inside an OS-level sandbox so that
        any harmful payload cannot escape to the host environment.
    """

    def __init__(self, cfg: dict[str, Any] | None = None) -> None:
        cfg = cfg or {}
        self._stage1_enabled: bool = cfg.get("security_stage1_enabled", True)
        self._stage2_enabled: bool = cfg.get("security_stage2_enabled", True)
        self._scanner = ContentScanner()
        try:
            self._sandbox = Sandbox(backend=cfg.get("sandbox_backend", "auto"))
        except SecurityInitializationError as exc:
            print(
                f"[security] FATAL gate initialization error: {exc}",
                file=sys.stderr,
            )
            sys.exit(1)
        except SystemExit:
            raise
        except Exception as exc:  # noqa: BLE001
            print(
                f"[security] FATAL gate initialization error: {exc}",
                file=sys.stderr,
            )
            sys.exit(1)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def open_url(self, url: str) -> GateResult:
        """Run the two-stage check and (if safe) open *url* in the sandbox."""
        stage1 = self._scan_url(url)
        if stage1 and stage1.is_blocked:
            return GateResult(
                allowed=False,
                stage1=stage1,
                reason="; ".join(stage1.reasons),
            )
        warnings = stage1.reasons if stage1 else []
        stage2 = self._sandbox_url(url) if self._stage2_enabled else None
        allowed = stage2.success if stage2 is not None else True
        reason = stage2.error if stage2 and not stage2.success else ""
        return GateResult(allowed=allowed, stage1=stage1, stage2=stage2, reason=reason, warnings=warnings)

    def open_file(self, path: str) -> GateResult:
        """Run the two-stage check and (if safe) open *path* in the sandbox."""
        stage1 = self._scan_file(path)
        if stage1 and stage1.is_blocked:
            return GateResult(
                allowed=False,
                stage1=stage1,
                reason="; ".join(stage1.reasons),
            )
        warnings = stage1.reasons if stage1 else []
        stage2 = self._sandbox_file(path) if self._stage2_enabled else None
        allowed = stage2.success if stage2 is not None else True
        reason = stage2.error if stage2 and not stage2.success else ""
        return GateResult(allowed=allowed, stage1=stage1, stage2=stage2, reason=reason, warnings=warnings)

    def check_text(self, text: str) -> GateResult:
        """Stage-1-only check for arbitrary text (email body, chat message, etc.)."""
        stage1 = self._scanner.scan_text(text) if self._stage1_enabled else None
        if stage1 and stage1.is_blocked:
            return GateResult(allowed=False, stage1=stage1, reason="; ".join(stage1.reasons))
        warnings = stage1.reasons if stage1 else []
        blocked = stage1 is not None and stage1.verdict == Verdict.BLOCKED
        return GateResult(allowed=not blocked, stage1=stage1, warnings=warnings)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _scan_url(self, url: str) -> ScanResult | None:
        return self._scanner.scan_url(url) if self._stage1_enabled else None

    def _scan_file(self, path: str) -> ScanResult | None:
        return self._scanner.scan_file(path) if self._stage1_enabled else None

    def _sandbox_url(self, url: str) -> SandboxResult:
        return self._sandbox.open_url(url)

    def _sandbox_file(self, path: str) -> SandboxResult:
        return self._sandbox.open_file(path)
