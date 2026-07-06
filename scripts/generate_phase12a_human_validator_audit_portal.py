#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_ID = "upi_dispute_resolution"
PORTAL = ROOT / "workspace" / "factory_generated" / APP_ID / "audit_portal" / "human_validator_audit_portal.html"


def main() -> int:
    if not PORTAL.exists():
        raise FileNotFoundError(f"Missing portal template: {PORTAL}")
    print(PORTAL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
