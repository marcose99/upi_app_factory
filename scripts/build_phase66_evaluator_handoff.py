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
    from upi_factory.rubric_alignment.handoff import build_handoff

    parser = argparse.ArgumentParser(description="Build Phase 66 evaluator handoff bundle.")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if not args.output_dir.is_absolute():
        raise SystemExit("--output-dir must be an absolute path")
    manifest = build_handoff(args.output_dir)
    print(json.dumps({"output_dir": str(args.output_dir), "file_count": len(manifest["files"])}, indent=2))


if __name__ == "__main__":
    main()
