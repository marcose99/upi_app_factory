from __future__ import annotations

import json
from pathlib import Path

from factory.application_engineering.deep_composer import DeepApplicationComposer
from factory.architecture_decisioning import BOUNDED_CLAIM_STATUS
from tests.architecture_decisioning import test_m2_1a_c3_realization_conformance as c3


WORKFLOW = "WORKFLOW_CENTRIC_MODULAR_MONOLITH"


def test_composer_emits_verified_architecture_dossier_and_manifest_claim_scope(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "generated"
    package = c3.reviewed_package(WORKFLOW)
    manifest = DeepApplicationComposer(c3.ROOT).compose(
        requirements_ir=c3.requirements_ir(),
        output_root=output_root,
        app_id="dossier_probe",
        architecture_package=package,
    )
    root = output_root / "dossier_probe"
    dossier_path = root / "evidence/architecture/architecture_decision_dossier.json"
    markdown_path = root / "docs/architecture/architecture_decision_dossier.md"
    assert dossier_path.is_file() and markdown_path.is_file()
    dossier = json.loads(dossier_path.read_text(encoding="utf-8"))
    assert dossier["architecture_claim_status"] == BOUNDED_CLAIM_STATUS
    assert dossier["nfr_sufficiency_gate"]["gate_outcome"] == "PASS_BOUNDED_CLAIM_REQUIRED"
    assert dossier["architecture_conformance"]["status"] == "PASS"
    assert dossier["global_optimum_claim_allowed"] is False
    assert manifest["architecture_decision_dossier_digest"] == dossier["dossier_digest"]
    assert manifest["architecture_claim_status"] == BOUNDED_CLAIM_STATUS
    assert manifest["architecture_nfr_sufficiency_gate_outcome"] == (
        "PASS_BOUNDED_CLAIM_REQUIRED"
    )
    markdown = markdown_path.read_text(encoding="utf-8")
    assert BOUNDED_CLAIM_STATUS in markdown
    assert "Candidate decision matrix" in markdown
    assert "Reconsideration triggers" in markdown
