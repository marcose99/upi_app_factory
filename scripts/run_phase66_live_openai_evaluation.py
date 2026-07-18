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
    from upi_factory.rubric_alignment.live import run_live_openai_evaluation

    parser = argparse.ArgumentParser(description="Run guarded Phase 66 live OpenAI evaluation.")
    parser.add_argument("--approve-live-openai-evaluation", action="store_true")
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--llm-model", required=True)
    parser.add_argument("--embedding-model", default="text-embedding-3-small")
    parser.add_argument("--max-llm-calls", type=int, default=45)
    args = parser.parse_args()
    result = run_live_openai_evaluation(
        args.output_root,
        approved=args.approve_live_openai_evaluation,
        llm_model=args.llm_model,
        embedding_model=args.embedding_model,
        max_llm_calls=args.max_llm_calls,
    )
    print(f"Phase 66 live OpenAI evaluation complete: {result['runtime']} -> {args.output_root}")


if __name__ == "__main__":
    main()
