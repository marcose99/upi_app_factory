#!/usr/bin/env python3
from __future__ import annotations

import json

from factory.operator_portal.evidence_dashboard import build_dashboard_summary


def main() -> int:
    print(json.dumps(build_dashboard_summary(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
