#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

def main() -> None:
    from upi_factory.rubric_alignment.validation import validate_phase66

    parser = argparse.ArgumentParser(description="Validate Phase 66 rubric-alignment artifacts.")
    parser.add_argument("--require-live-evidence", action="store_true")
    args = parser.parse_args()
    result = validate_phase66(require_live_evidence=args.require_live_evidence)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
