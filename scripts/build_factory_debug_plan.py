#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--json-out", type=Path, required=True)
    parser.add_argument("--text-out", type=Path, required=True)
    args = parser.parse_args(argv)

    debugging = importlib.import_module("factory.debugging")
    debug_plan = importlib.import_module("factory.debugging.debug_plan")
    plan = debugging.build_factory_debug_plan(args.project_root.resolve())
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.text_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.text_out.write_text(debug_plan.render_debug_plan_markdown(plan), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
