#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from factory.operator_portal.web_ui import create_web_ui_app  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the Phase 36 local-only operator portal web UI.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Local bind host.")
    parser.add_argument("--port", default=8036, type=int, help="Local bind port.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.host not in {"127.0.0.1", "localhost"}:
        raise SystemExit("Phase 36 local web UI only supports loopback hosts.")

    import uvicorn

    uvicorn.run(create_web_ui_app(project_root=PROJECT_ROOT), host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
