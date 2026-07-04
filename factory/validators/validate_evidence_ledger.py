from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    path = Path("evidence/evidence_ledger.jsonl")
    errors: list[str] = []
    if not path.exists():
        errors.append("evidence ledger missing")
    else:
        for line_no, line in enumerate(path.read_text().splitlines(), start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"invalid json line {line_no}: {exc}")
                continue
            for field in ["evidence_id", "source_type", "title", "status"]:
                if field not in record:
                    errors.append(f"line {line_no} missing {field}")
    print(json.dumps({"passed": not errors, "errors": errors}, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
