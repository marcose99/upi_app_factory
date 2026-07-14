from __future__ import annotations
from typing import Any

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = ROOT / "scripts" / "validate_phase12a_independent_audit_foundation.py"


def load_validator() -> Any:
    spec = importlib.util.spec_from_file_location(
        "validate_phase12a_independent_audit_foundation",
        VALIDATOR_PATH,
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_phase12a_independent_audit_foundation_passes() -> None:
    validator = load_validator()
    result = validator.validate()
    assert result["passed"], json.dumps(result, indent=2, sort_keys=True)


def test_phase12a_portal_exists_and_is_offline() -> None:
    portal = ROOT / "workspace" / "factory_generated" / "upi_dispute_resolution" / "audit_portal" / "human_validator_audit_portal.html"
    text = portal.read_text(encoding="utf-8")
    assert "upi_app_factory" in text
    assert "https://" not in text
    assert "Animated Agentic Factory Flow" in text


def test_phase12a_audit_control_catalog_has_two_subjects() -> None:
    catalog = ROOT / "docs" / "phase12a" / "audit_control_catalog.json"
    data = json.loads(catalog.read_text(encoding="utf-8"))
    assert data["audit_subjects"] == ["agentic_ai_factory", "generated_upi_application"]
