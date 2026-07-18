#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for candidate in (ROOT, SRC):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from upi_factory.capstone.phase69 import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main(["--validate-only", *sys.argv[1:]]))
