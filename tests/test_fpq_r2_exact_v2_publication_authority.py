from __future__ import annotations

import inspect
import json
import re
from pathlib import Path

import pytest

from factory import exact_v2_traceability as exact_v2
from factory import generated_application_artifacts as artifacts
from scripts import run_portal_requirements_driven_application_engineering as portal


ROOT = Path(__file__).resolve().parents[1]


def _portal_config(tmp_path: Path) -> portal.AdapterConfig:
    requirements = tmp_path / "requirements.md"
    requirements.write_text(
        """# Authoritative failed-debit runtime

Build and register the authoritative local failed-debit runtime with evidence
collection, investigation, human review, disposition, audit verification,
closure, mock-only payment boundaries, and deterministic local test proof.
""",
        encoding="utf-8",
    )
    return portal.AdapterConfig(
        requirements=requirements,
        app_id="upi_dispute_resolution",
        output_root=tmp_path / "published_application",
        evidence_root=tmp_path / "publication_evidence",
        approval_mode="human-gated",
        approval_token=portal.APPROVAL_TOKEN,
        mock_safe=True,
        plan_only=False,
        replace_existing=False,
        factory_root=ROOT,
        workspace_root=tmp_path,
        portfolio_state_root=tmp_path / "portfolio",
        engineering_profile="authoritative-failed-debit-v1",
        register_with_portfolio=True,
    )


def test_publication_api_has_one_fail_closed_mode() -> None:
    forbidden_parameters = {"converged", "converge_exact_input"}
    for callable_object in (
        exact_v2.build_atomic_obligation_inventory,
        artifacts.build_generated_application_artifact_payloads,
        artifacts.materialize_generated_application_artifacts,
        exact_v2._classify_support,
    ):
        assert not forbidden_parameters & set(inspect.signature(callable_object).parameters)

    legacy_builder = "build_" + "converged_generated_application_artifact_payloads"
    legacy_materializer = "materialize_" + "converged_generated_application_artifacts"
    for module in (exact_v2, artifacts):
        assert not hasattr(module, legacy_builder)
        assert not hasattr(module, legacy_materializer)
    assert legacy_builder not in artifacts.__all__
    assert legacy_materializer not in artifacts.__all__


def test_generic_section_references_cannot_manufacture_atomic_support(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    implementation = "implementation.py"
    test_reference = "test_generic.py"
    evidence = "evidence.json"
    (tmp_path / implementation).write_text("generic section implementation\n", encoding="utf-8")
    (tmp_path / test_reference).write_text("generic section test\n", encoding="utf-8")
    (tmp_path / evidence).write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(
        exact_v2,
        "SECTION_REFERENCE_RULES",
        (
            {
                "sections": ("9",),
                "implementation_paths": (implementation,),
                "test_references": (test_reference,),
                "evidence_references": (evidence,),
            },
        ),
    )

    classification = exact_v2._classify_support(
        obligation={
            "source": {"section": "9. Atomic control"},
            "normalized_text": "UniqueAtomicControlZXQ must be enforced.",
        },
        project_root=tmp_path,
        openapi_inventory={"endpoint_inventory": []},
        file_index={
            implementation: "generic section implementation",
            test_reference: "generic section test",
        },
        generated_relative_paths={evidence},
    )

    assert classification["support_status"] == "PARTIAL"
    assert classification["implementation_refs"] == []
    assert classification["test_refs"] == []
    assert classification["evidence_refs"] == [{"path": evidence}]
    assert classification["support_binding"] is None


def _classify_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    obligation_text: str,
    implementation_text: str,
    test_text: str,
    openapi_inventory: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    implementation = "implementation.py"
    test_reference = "test_binding.py"
    evidence = "evidence.json"
    (tmp_path / implementation).write_text(implementation_text, encoding="utf-8")
    (tmp_path / test_reference).write_text(test_text, encoding="utf-8")
    (tmp_path / evidence).write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(
        exact_v2,
        "SECTION_REFERENCE_RULES",
        (
            {
                "sections": ("9",),
                "implementation_paths": (implementation,),
                "test_references": (test_reference,),
                "evidence_references": (evidence,),
            },
        ),
    )
    return exact_v2._classify_support(
        obligation={
            "source": {"section": "9. Atomic control"},
            "normalized_text": obligation_text,
        },
        project_root=tmp_path,
        openapi_inventory={"endpoint_inventory": openapi_inventory or []},
        file_index={
            implementation: implementation_text,
            test_reference: test_text,
        },
        generated_relative_paths={evidence},
    )


def test_shared_distinctive_identifier_produces_one_atomic_binding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    classification = _classify_fixture(
        tmp_path,
        monkeypatch,
        obligation_text="UniqueAtomicControlZXQ must be enforced.",
        implementation_text="unique_atomic_control_zxq = True\n",
        test_text=(
            "def test_unique_atomic_control() -> None:\n"
            "    assert 'unique_atomic_control_zxq'\n"
        ),
    )

    assert classification["support_status"] == "SUPPORTED"
    assert classification["support_binding"] == {
        "binding_key": "UniqueAtomicControlZXQ",
        "binding_type": "identifier",
        "implementation_paths": ["implementation.py"],
        "test_references": ["test_binding.py"],
    }


def test_different_distinctive_identifiers_cannot_be_combined(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    classification = _classify_fixture(
        tmp_path,
        monkeypatch,
        obligation_text=(
            "ImplementationOnlyZXQ must be verified by TestOnlyZXQ."
        ),
        implementation_text="ImplementationOnlyZXQ = True\n",
        test_text=(
            "def test_distinctive_control() -> None:\n"
            "    assert 'TestOnlyZXQ'\n"
        ),
    )

    assert classification["support_status"] == "PARTIAL"
    assert classification["support_binding"] is None


def test_shared_generic_domain_term_cannot_prove_support(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    classification = _classify_fixture(
        tmp_path,
        monkeypatch,
        obligation_text="payment evidence must be supported",
        implementation_text="payment evidence\n",
        test_text=(
            "def test_generic_domain_terms() -> None:\n"
            "    assert 'payment evidence'\n"
        ),
    )

    assert classification["support_status"] == "PARTIAL"
    assert classification["support_binding"] is None


def test_endpoint_binding_also_requires_exact_openapi_operation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    obligation_text = "POST /v1/distinctive-controls"
    implementation_text = (
        '@app.post("/v1/distinctive-controls")\ndef create(): ...\n'
    )
    test_text = (
        "def test_distinctive_endpoint() -> None:\n"
        "    client.post('/v1/distinctive-controls')\n"
    )
    missing_openapi = _classify_fixture(
        tmp_path,
        monkeypatch,
        obligation_text=obligation_text,
        implementation_text=implementation_text,
        test_text=test_text,
    )
    assert missing_openapi["support_status"] == "PARTIAL"
    assert missing_openapi["support_binding"] is None

    exact_openapi = _classify_fixture(
        tmp_path,
        monkeypatch,
        openapi_inventory=[
            {"method": "POST", "path": "/v1/distinctive-controls"}
        ],
        obligation_text=obligation_text,
        implementation_text=implementation_text,
        test_text=test_text,
    )
    assert exact_openapi["support_status"] == "SUPPORTED"
    binding = exact_openapi["support_binding"]
    assert isinstance(binding, dict)
    assert binding["binding_key"] == "POST /v1/distinctive-controls"
    assert binding["binding_type"] == "endpoint"



def test_explicit_state_transition_cannot_fall_back_to_state_identifier(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    classification = _classify_fixture(
        tmp_path,
        monkeypatch,
        obligation_text="CLOSED -> INVESTIGATING",
        implementation_text=(
            'FAILED_DEBIT_ALLOWED_TRANSITIONS = {'
            '"CLOSED": set(), "INVESTIGATING": {"VALIDATED"}}\n'
        ),
        test_text=(
            "def test_investigating_state_exists() -> None:\n"
            "    assert 'INVESTIGATING'\n"
        ),
    )

    assert classification["support_status"] == "PARTIAL"
    assert classification["support_binding"] is None


def test_exact_state_transition_binding_remains_supported(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    classification = _classify_fixture(
        tmp_path,
        monkeypatch,
        obligation_text="INITIATED -> INVESTIGATING",
        implementation_text=(
            'FAILED_DEBIT_ALLOWED_TRANSITIONS = {'
            '"INITIATED": {"INVESTIGATING"}}\n'
        ),
        test_text=(
            "def test_initiated_to_investigating() -> None:\n"
            "    assert transition('INITIATED', 'INVESTIGATING')\n"
        ),
    )

    assert classification["support_status"] == "SUPPORTED"
    binding = classification["support_binding"]
    assert isinstance(binding, dict)
    assert binding["binding_key"] == "INITIATED -> INVESTIGATING"
    assert binding["binding_type"] == "state_transition"


def test_compound_identifier_constraint_cannot_fall_back_to_one_identifier(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    classification = _classify_fixture(
        tmp_path,
        monkeypatch,
        obligation_text="impact is HIGH or CRITICAL",
        implementation_text="impact = HIGH\n",
        test_text=(
            "def test_high_impact() -> None:\n"
            "    assert impact == HIGH\n"
        ),
    )

    assert classification["support_status"] == "PARTIAL"
    assert classification["support_binding"] is None


def test_authoritative_supported_bindings_are_collision_free() -> None:
    payloads = artifacts.build_generated_application_artifact_payloads(ROOT)
    inventory = json.loads(payloads["evidence/atomic_obligation_inventory.json"])
    rows = inventory["items"]
    observed = {row["obligation_id"]: row for row in rows}

    assert observed["OBL-P08-7-028"]["support_status"] == "PARTIAL"
    assert observed["OBL-P08-7-028"]["support_binding"] is None
    assert observed["OBL-P12-12-017"]["support_status"] != "SUPPORTED"

    owners: dict[str, str] = {}
    for row in rows:
        if row["support_status"] != "SUPPORTED":
            continue
        binding = row["support_binding"]
        assert isinstance(binding, dict)
        canonical = exact_v2._canonical_binding_text(binding["binding_key"])
        prior_owner = owners.get(canonical)
        assert prior_owner is None or prior_owner == row["obligation_id"]
        owners[canonical] = row["obligation_id"]

        transitions = exact_v2.TRANSITION_RE.findall(row["normalized_text"])
        if transitions:
            assert len(transitions) == 1
            assert binding["binding_type"] == "state_transition"
            source_state, target_state = transitions[0]
            assert binding["binding_key"] == f"{source_state} -> {target_state}"

        identifiers = {
            exact_v2._canonical_binding_text(match.group(0))
            for match in exact_v2.TOKEN_RE.finditer(row["normalized_text"])
        }
        if (
            len(identifiers) > 1
            and re.search(
                r"\b(?:and|or)\b",
                row["normalized_text"],
                re.IGNORECASE,
            )
        ):
            assert binding["binding_type"] != "identifier"



def test_actual_supported_rows_have_valid_shared_bindings() -> None:
    payloads = artifacts.build_generated_application_artifact_payloads(ROOT)
    inventory = json.loads(payloads["evidence/atomic_obligation_inventory.json"])
    rows = inventory["items"]
    bindings_by_id = {
        row["obligation_id"]: row["support_binding"]
        for row in rows
    }
    propagated_surfaces = (
        (
            json.loads(
                payloads["evidence/requirements_traceability_matrix.json"]
            )["items"],
            "obligation_id",
        ),
        (
            json.loads(payloads["evidence/classification_decision_table.json"])[
                "items"
            ],
            "obligation_id",
        ),
        (
            json.loads(payloads["evidence/CAPABILITY_PRE_RUN_REPORT.json"])[
                "obligations"
            ],
            "id",
        ),
        (
            json.loads(payloads["evidence/REQUIREMENT_CAPABILITY_MATRIX.json"])[
                "items"
            ],
            "id",
        ),
    )
    for surface_rows, identifier_field in propagated_surfaces:
        assert all(
            row["support_binding"] == bindings_by_id[row[identifier_field]]
            for row in surface_rows
        )
    prior_cross_token_false_supports = {
        "OBL-P01-4-001",
        "OBL-P02-10-009",
        "OBL-P04-4-032",
        "OBL-P22-26-053",
        "OBL-P23-26-057",
    }
    observed = {row["obligation_id"]: row for row in rows}
    assert all(
        observed[obligation_id]["support_status"] == "PARTIAL"
        and observed[obligation_id]["support_binding"] is None
        for obligation_id in prior_cross_token_false_supports
    )

    supported_rows = [row for row in rows if row["support_status"] == "SUPPORTED"]
    assert supported_rows
    for row in rows:
        assert "support_binding" in row
        binding = row["support_binding"]
        if row["support_status"] != "SUPPORTED":
            assert binding is None
            continue
        assert set(binding) == {
            "binding_key",
            "binding_type",
            "implementation_paths",
            "test_references",
        }
        assert binding["binding_type"] in exact_v2.BINDING_TYPES
        assert exact_v2._binding_is_distinctive(binding["binding_key"])
        assert exact_v2._binding_occurs(
            binding["binding_key"],
            row["normalized_text"],
        )
        assert binding["implementation_paths"] == row["implementation_paths"]
        assert binding["test_references"] == row["test_references"]
        assert all(
            exact_v2._binding_occurs(
                binding["binding_key"],
                (ROOT / path).read_text(encoding="utf-8"),
            )
            for path in binding["implementation_paths"]
        )
        assert all(
            exact_v2._binding_occurs(
                binding["binding_key"],
                (ROOT / nodeid.partition("::")[0]).read_text(encoding="utf-8"),
            )
            for nodeid in binding["test_references"]
        )


def test_authoritative_payloads_and_materializer_are_consistent(tmp_path: Path) -> None:
    payloads = artifacts.build_generated_application_artifact_payloads(ROOT)
    assert set(payloads) == set(artifacts.REQUIRED_ARTIFACT_RELATIVE_PATHS)
    assert "evidence/generation_summary.json" in payloads

    forbidden_claim = "PROVEN_" + "100_PERCENT_CAPABILITY"
    for relative_path, content in payloads.items():
        assert forbidden_claim not in content
        if relative_path == "generation_metadata.json" or (
            relative_path.startswith("evidence/") and relative_path.endswith(".json")
        ):
            surface = json.loads(content)
            assert surface["evidence_authority"] == artifacts.EVIDENCE_AUTHORITY
            assert surface["publication_authority"] is True
            assert surface["diagnostic_projection_used"] is False

    output = tmp_path / "generated_application"
    result = artifacts.materialize_generated_application_artifacts(
        ROOT,
        application_root=output,
    )
    for relative_path, content in payloads.items():
        assert (output / relative_path).read_text(encoding="utf-8") == content
    assert result["exact_v2_evidence_decision"] == artifacts.NO_GO_EVIDENCE_DECISION
    assert result["exact_v2_evidence_authority"] == artifacts.EVIDENCE_AUTHORITY
    assert result["exact_v2_mandatory_gate_passed"] is False
    assert result["definition_of_done_status"] == "definition_of_done_blocked"


def test_portal_rejects_diagnostic_projection_as_publication_authority() -> None:
    materialization = {
        "evidence_authority": artifacts.EVIDENCE_AUTHORITY,
        "publication_authority": True,
        "diagnostic_projection_used": True,
        "definition_of_done_status": "definition_of_done_blocked",
        "exact_v2_evidence_decision": artifacts.NO_GO_EVIDENCE_DECISION,
        "exact_v2_evidence_authority": artifacts.EVIDENCE_AUTHORITY,
        "exact_v2_mandatory_gate_passed": False,
    }
    with pytest.raises(portal.AdapterError, match="diagnostic_projection_used"):
        portal._validate_exact_v2_publication_authority(materialization)

    run_source = inspect.getsource(portal.run)
    assert "materialize_generated_application_artifacts" in run_source
    assert "materialize_" + "converged_generated_application_artifacts" not in run_source


def test_portal_rejects_quarantined_materialization_and_manifest() -> None:
    quarantined_root = (
        ROOT
        / "workspace"
        / "factory_generated"
        / "upi_dispute_resolution"
        / "generated_application"
        / artifacts.QUARANTINED_APPLICATION_SUBTREE
    )
    forged_materialization = {
        "evidence_authority": artifacts.EVIDENCE_AUTHORITY,
        "publication_authority": True,
        "diagnostic_projection_used": False,
        "definition_of_done_status": "definition_of_done_blocked",
        "exact_v2_evidence_decision": artifacts.NO_GO_EVIDENCE_DECISION,
        "exact_v2_evidence_authority": artifacts.EVIDENCE_AUTHORITY,
        "exact_v2_mandatory_gate_passed": False,
        "project_root": str(ROOT),
        "application_root": str(quarantined_root),
    }
    with pytest.raises(portal.AdapterError, match="quarantined"):
        portal._validate_exact_v2_publication_authority(forged_materialization)

    with pytest.raises(portal.AdapterError, match="publication manifest"):
        portal._validate_publication_manifest_quarantine(
            [
                {
                    "relative_path": (
                        "generated_application/current_definition_of_done/"
                        "generation_metadata.json"
                    ),
                    "size_bytes": 1,
                    "sha256": "0" * 64,
                }
            ]
        )


def test_portal_persists_authority_and_exact_builder_bytes(tmp_path: Path) -> None:
    result = portal.run(_portal_config(tmp_path))
    expected_fields = {
        "evidence_authority": artifacts.EVIDENCE_AUTHORITY,
        "publication_authority": True,
        "diagnostic_projection_used": False,
        "exact_v2_evidence_decision": artifacts.NO_GO_EVIDENCE_DECISION,
        "exact_v2_evidence_authority": artifacts.EVIDENCE_AUTHORITY,
        "exact_v2_mandatory_gate_passed": False,
    }
    for field, expected in expected_fields.items():
        assert result[field] == expected

    persisted = json.loads(
        (Path(str(result["evidence_directory"])) / "result.json").read_text(
            encoding="utf-8"
        )
    )
    registration = result["portfolio_registration"]
    assert isinstance(registration, dict)
    for field, expected in expected_fields.items():
        assert persisted[field] == expected
        assert registration[field] == expected

    payloads = artifacts.build_generated_application_artifact_payloads(ROOT)
    nested_application = Path(str(result["application_root"])) / "generated_application"
    assert not (
        nested_application / artifacts.QUARANTINED_APPLICATION_SUBTREE
    ).exists()
    for relative_path, content in payloads.items():
        assert (nested_application / relative_path).read_text(encoding="utf-8") == content
