#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from factory.operator_portal.evidence_dashboard import build_dashboard_summary  # noqa: E402


def main() -> int:
    print(json.dumps(build_dashboard_summary(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
