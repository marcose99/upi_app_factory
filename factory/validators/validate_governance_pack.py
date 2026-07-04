from __future__ import annotations

from pathlib import Path
import json
import sys


REQUIRED = [
    "factory_governance/01_PROJECT_CHARTER.md",
    "factory_governance/04_RISK_TIERS.yaml",
    "factory_governance/05_POLICY_REGISTRY.yaml",
    "factory_governance/07_MOCK_BOUNDARY_POLICY.yaml",
]


def main() -> int:
    errors = [f"missing: {p}" for p in REQUIRED if not Path(p).exists()]
    print(json.dumps({"passed": not errors, "errors": errors}, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
