from __future__ import annotations

import json
import sys
from app.feedback.repository import open_blockers


def main() -> int:
    errors: list[str] = []
    blockers = open_blockers()
    if blockers:
        errors.append(f"open BLOCKER feedback exists: {[b.feedback_id for b in blockers]}")
    print(json.dumps({"passed": not errors, "errors": errors}, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
