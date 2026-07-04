from __future__ import annotations

import json
import sys
from pathlib import Path
import yaml


def main() -> int:
    path = Path("factory_governance/05_POLICY_REGISTRY.yaml")
    errors: list[str] = []
    if not path.exists():
        errors.append("policy registry missing")
    else:
        data = yaml.safe_load(path.read_text()) or {}
        policies = data.get("policies", [])
        if not policies:
            errors.append("no policies found")
        for policy in policies:
            if "policy_id" not in policy or "rule" not in policy:
                errors.append(f"invalid policy: {policy}")
    print(json.dumps({"passed": not errors, "errors": errors}, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
