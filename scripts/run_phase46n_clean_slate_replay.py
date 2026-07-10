from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from tools.autonomous_supervisor.clean_slate import replay


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
    )
    parsed = parser.parse_args()
    state_root = Path(
        os.environ.get(
            "UPI_APP_FACTORY_STATE_DIR",
            str(Path.home() / ".local/state/upi_app_factory"),
        )
    ).resolve()
    python = (
        parsed.project_root.resolve() / ".venv/bin/python"
    )
    if not python.is_file():
        python = Path(sys.executable)
    report = replay(
        project_root=parsed.project_root.resolve(),
        state_root=state_root,
        python=python,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
