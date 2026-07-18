#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

def main() -> None:
    from upi_factory.rubric_alignment.benchmark import run_offline_evaluation

    parser = argparse.ArgumentParser(description="Run Phase 66 deterministic offline evaluation.")
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    result = run_offline_evaluation(args.output_root)
    print(f"Phase 66 offline evaluation complete: {result['runtime']} -> {args.output_root}")


if __name__ == "__main__":
    main()
