from __future__ import annotations

import sys
from pathlib import Path


GENERATED_APP_ROOT = Path(__file__).resolve().parents[1]
APP_SOURCE = GENERATED_APP_ROOT / "app"
APP_PARENT = GENERATED_APP_ROOT.parent

if str(APP_SOURCE) not in sys.path:
    sys.path.insert(0, str(APP_SOURCE))
if str(APP_PARENT) not in sys.path:
    sys.path.insert(0, str(APP_PARENT))
