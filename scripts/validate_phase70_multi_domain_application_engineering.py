#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for candidate in (PROJECT_ROOT, SRC_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from upi_factory.capstone.phase70 import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
