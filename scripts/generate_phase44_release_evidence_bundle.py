#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from factory.operator_portal.release_evidence_bundle import (  # noqa: E402
    write_release_evidence_bundle,
)


def main() -> int:
    bundle = write_release_evidence_bundle()
    print(
        json.dumps(
            {
                "phase": bundle["manifest"]["phase"],
                "status": "generated",
                "artifact_count": len(bundle["manifest"]["required_artifacts"]),
                "zip_export_created": bundle["manifest"]["zip_export_created"],
                "certification_boundary": bundle["manifest"]["certification_boundary"],
            },
            indent=2,
            sort_keys=True,
        ),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
