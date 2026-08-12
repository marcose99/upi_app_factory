from __future__ import annotations

import hashlib
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (PROJECT_ROOT / relative).read_text(encoding="utf-8")


def test_readme_documents_canonical_failed_debit_workflow_and_alias_limits() -> None:
    readme = _read("README.md")
    canonical_markers = (
        "/investigate",
        "/classify",
        "/human-review",
        "/review-decisions",
        "/disposition",
        "/close",
        "/history",
        "/audit-integrity",
    )
    assert all(marker in readme for marker in canonical_markers)
    assert "deprecated, schema-hidden compatibility aliases" in readme
    assert (
        "compatibility aliases for `/investigate`, `/classify`, and `/history`"
        in readme
    )
    assert "finalize_action=propose_only" in readme
    assert "delegates to classification" in readme
    assert "cannot record a disposition, finalize, or close a case" in readme

    api_source = _read(
        "workspace/factory_generated/upi_dispute_resolution/"
        "generated_application/app/interfaces/api/main.py"
    )
    compatibility_handler = api_source.split(
        "async def propose_failed_debit_resolution_compat(",
        1,
    )[1].split("\n\n", 1)[0]
    assert "return await classify_failed_debit_case(" in compatibility_handler
    assert "record_failed_debit_disposition(" not in compatibility_handler


def test_current_recipient_guidance_states_complete_native_and_offline_contract() -> None:
    for relative in (
        "README.md",
        "docs/handover/ENVIRONMENT_SPEC.md",
        "docs/handover/QUICKSTART.md",
    ):
        text = _read(relative)
        assert "Git" in text
        assert "Python 3.10 or newer" in text
        assert "venv" in text
        assert "pip" in text
        assert "write access" in text
        assert "exact locked" in text
        assert "offline" in text.lower()
        assert "Docker" in text


def test_documentation_evidence_hashes_match_current_documents() -> None:
    matrix = json.loads(
        _read("docs/documentation/DOCUMENTATION_EVIDENCE_MATRIX.json")
    )
    records = {item["path"]: item for item in matrix["documents"]}
    for relative in (
        "README.md",
        "docs/handover/ENVIRONMENT_SPEC.md",
        "docs/handover/QUICKSTART.md",
    ):
        assert records[relative]["classification_after"] == "CURRENT_AND_VERIFIED"
        assert records[relative]["sha256_after"] == hashlib.sha256(
            (PROJECT_ROOT / relative).read_bytes()
        ).hexdigest()
