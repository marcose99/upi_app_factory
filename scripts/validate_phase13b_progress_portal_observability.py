#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
APP_ID = "upi_dispute_resolution"
RUN_ID = "first_governed_generation_run_001"
FACTORY_ROOT = ROOT / "workspace" / "factory_generated" / APP_ID
PHASE_DOCS = ROOT / "docs" / "phase13b"
RUN_ROOT = FACTORY_ROOT / "generation_runs" / RUN_ID
PORTAL = FACTORY_ROOT / "audit_portal" / "factory_generation_progress_portal.html"


def validate() -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    required = [
        PHASE_DOCS / "factory_progress_observability_portal_contract.json",
        PHASE_DOCS / "factory_progress_observability_snapshot.json",
        RUN_ROOT / "factory_progress_observability_snapshot.json",
        PORTAL,
    ]
    for path in required:
        if not path.exists():
            errors.append({"path": str(path.relative_to(ROOT)), "error": "missing_file"})

    if PORTAL.exists():
        text = PORTAL.read_text(encoding="utf-8")
        for term in [
            "Factory Progress Portal",
            "Completion Gauges",
            "Validation Bar Chart",
            "Observability Readiness Chart",
            "Factory Maturity Trend",
            "Application Generation Metrics",
            "conic-gradient",
            "<svg",
            "deterministic scripted generation",
        ]:
            if term not in text:
                errors.append({"path": str(PORTAL.relative_to(ROOT)), "error": f"missing:{term}"})

    contract = PHASE_DOCS / "factory_progress_observability_portal_contract.json"
    if contract.exists():
        data = json.loads(contract.read_text(encoding="utf-8"))
        for visual in ["validation_bar_chart", "maturity_trend_svg", "completion_donuts"]:
            if visual not in data["required_visuals"]:
                errors.append({"path": str(contract.relative_to(ROOT)), "error": f"missing_visual:{visual}"})

    return {
        "passed": not errors,
        "phase": "Phase 13B",
        "portal": str(PORTAL.relative_to(ROOT)),
        "errors": errors,
    }


def main() -> int:
    result = validate()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
