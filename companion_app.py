"""Legacy compatibility shim for Aura Nexus.

Delegates to `aura_nexus_app.main` so any stale shortcuts continue to
work. Safe to remove once all external references are updated.
"""

from __future__ import annotations

import sys


def main() -> int:  # pragma: no cover
    try:
        from aura_nexus_app import main as aura_main
    except Exception as e:
        print("[Aura Nexus] Please launch via run_aura_nexus.ps1", file=sys.stderr)
        print(f"Import error: {e}", file=sys.stderr)
        return 1
    return aura_main()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())