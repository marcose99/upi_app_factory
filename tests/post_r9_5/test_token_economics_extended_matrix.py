from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import unittest

from factory.token_economics import (
    LedgerStore,
    load_artifact_ownership_registry,
    load_governance_policy,
    resolve_artifact_owner,
)


ROOT = Path(__file__).resolve().parents[2]
TOKEN_CONFIG_ROOT = ROOT / "config" / "token_economics"
EXPECTED_EXTENDED_TRACEABILITY = {
    "TE-031": {
        "description": "artifact owner exactness resolves to one declared family only",
        "references": [
            "tests/post_r9_5/test_token_economics_extended_matrix.py::TokenEconomicsExtendedMatrixTest::test_exact_artifact_owner_resolution_and_runtime_commit_exclusion"
        ],
    },
    "TE-032": {
        "description": "path-pattern prefix collisions fail closed",
        "references": [
            "tests/post_r9_5/test_token_economics_extended_matrix.py::TokenEconomicsExtendedMatrixTest::test_prefix_collisions_fail_closed"
        ],
    },
    "TE-033": {
        "description": "symlinked artifacts are rejected",
        "references": [
            "tests/test_token_economics_core_governance.py::test_validate_artifact_path_uses_governed_registry_and_rejects_escape"
        ],
    },
    "TE-034": {
        "description": "tracked evidence restoration removes runtime drift",
        "references": [
            "tests/test_prerequisite_artifact_materializer.py::test_mutable_runtime_snapshot_restores_changed_files_and_removes_new_paths"
        ],
    },
    "TE-035": {
        "description": "staged runtime outputs are excluded from candidate-commit artifacts",
        "references": [
            "tests/post_r9_5/test_token_economics_extended_matrix.py::TokenEconomicsExtendedMatrixTest::test_exact_artifact_owner_resolution_and_runtime_commit_exclusion"
        ],
    },
    "TE-036": {
        "description": "historical settlements remain append-only and immutable",
        "references": [
            "tests/post_r9_5/test_token_economics_extended_matrix.py::TokenEconomicsExtendedMatrixTest::test_ledger_history_is_append_only"
        ],
    },
    "TE-037": {
        "description": "budget exceptions require scoped human authority",
        "references": [
            "tests/post_r9_5/test_token_economics_extended_matrix.py::TokenEconomicsExtendedMatrixTest::test_governance_policy_preserves_scoped_budget_exceptions_and_legal_hold"
        ],
    },
    "TE-038": {
        "description": "retention and legal-hold policy remain machine-readable",
        "references": [
            "tests/post_r9_5/test_token_economics_extended_matrix.py::TokenEconomicsExtendedMatrixTest::test_governance_policy_preserves_scoped_budget_exceptions_and_legal_hold"
        ],
    },
    "TE-039": {
        "description": "migration compatibility mappings are preserved",
        "references": [
            "tests/post_r9_5/test_token_economics_extended_matrix.py::TokenEconomicsExtendedMatrixTest::test_governance_policy_preserves_migration_compatibility"
        ],
    },
    "TE-040": {
        "description": "rate-card publication remains a human-authority decision right",
        "references": [
            "tests/post_r9_5/test_token_economics_extended_matrix.py::TokenEconomicsExtendedMatrixTest::test_rate_publication_and_certification_claims_stay_human_gated"
        ],
    },
    "TE-041": {
        "description": "certification claims remain human-authority gated",
        "references": [
            "tests/post_r9_5/test_token_economics_extended_matrix.py::TokenEconomicsExtendedMatrixTest::test_rate_publication_and_certification_claims_stay_human_gated"
        ],
    },
    "TE-042": {
        "description": "compact logs default to restricted-content exclusion",
        "references": [
            "tests/test_token_economics_core_governance.py::test_ledger_duplicate_guard_and_compact_redaction_fail_closed"
        ],
    },
    "TE-043": {
        "description": "generated application applicability remains truthful and explicit",
        "references": [
            "tests/test_token_economics_governed_surfaces.py::test_generated_application_token_economics_applicability_requires_declared_model_activity"
        ],
    },
    "TE-044": {
        "description": "operator visibility separates budget controls from runtime usage views",
        "references": [
            "tests/test_token_economics_core_governance.py::test_summary_and_dashboard_expose_operator_visibility_contracts"
        ],
    },
    "TE-045": {
        "description": "operator summary stays local, deterministic, and mock-only",
        "references": [
            "tests/test_token_economics_governed_surfaces.py::test_token_economics_summary_stays_local_mock_only_and_deterministic"
        ],
    },
    "TE-046": {
        "description": "model-version migration still requires explicit rate-card matching",
        "references": [
            "tests/test_token_economics_mandatory_matrix.py::test_model_version_migration_requires_explicit_rate_card_match"
        ],
    },
    "TE-047": {
        "description": "governed artifact registry remains declared and non-empty",
        "references": [
            "tests/post_r9_5/test_token_economics_extended_matrix.py::TokenEconomicsExtendedMatrixTest::test_registry_declares_multiple_governed_families"
        ],
    },
    "TE-048": {
        "description": "runtime-root artifact families remain non-committable",
        "references": [
            "tests/post_r9_5/test_token_economics_extended_matrix.py::TokenEconomicsExtendedMatrixTest::test_exact_artifact_owner_resolution_and_runtime_commit_exclusion"
        ],
    },
    "TE-049": {
        "description": "the extended matrix preserves the existing 30-case semantics",
        "references": [
            "tests/post_r9_5/test_token_economics_extended_matrix.py::TokenEconomicsExtendedMatrixTest::test_extended_matrix_preserves_legacy_base_cases_and_adds_te_031_through_te_049"
        ],
    },
}


class TokenEconomicsExtendedMatrixTest(unittest.TestCase):
    def test_extended_matrix_preserves_legacy_base_cases_and_adds_te_031_through_te_049(self) -> None:
        payload = json.loads((TOKEN_CONFIG_ROOT / "mandatory_test_matrix.json").read_text(encoding="utf-8"))

        base_cases = payload["cases"]
        extended_cases = payload["extended_cases"]
        self.assertEqual([item["case_id"] for item in base_cases], [f"TE-{index:03d}" for index in range(1, 31)])
        self.assertEqual(
            [item["case_id"] for item in extended_cases],
            [f"TE-{index:03d}" for index in range(31, 50)],
        )
        self.assertEqual(len(base_cases) + len(extended_cases), 49)

    def test_extended_matrix_traceability_explicitly_covers_te_031_through_te_049(self) -> None:
        payload = json.loads((TOKEN_CONFIG_ROOT / "mandatory_test_matrix.json").read_text(encoding="utf-8"))

        extended_cases = {item["case_id"]: item for item in payload["extended_cases"]}
        self.assertEqual(set(extended_cases), set(EXPECTED_EXTENDED_TRACEABILITY))
        for case_id, expected in EXPECTED_EXTENDED_TRACEABILITY.items():
            case = extended_cases[case_id]
            self.assertEqual(case["coverage_kind"], "automated_test")
            self.assertEqual(case["description"], expected["description"])
            self.assertEqual(case["references"], expected["references"])
            for reference in case["references"]:
                path_text = reference.split("::", 1)[0]
                self.assertTrue((ROOT / path_text).is_file(), reference)

    def test_registry_declares_multiple_governed_families(self) -> None:
        registry = load_artifact_ownership_registry(TOKEN_CONFIG_ROOT)
        self.assertGreaterEqual(len(registry["families"]), 4)

    def test_exact_artifact_owner_resolution_and_runtime_commit_exclusion(self) -> None:
        owned = resolve_artifact_owner("config/token_economics/governance_policy.json", config_root=TOKEN_CONFIG_ROOT)
        runtime = resolve_artifact_owner(
            "workspace/token_economics_runtime/ledger.jsonl",
            config_root=TOKEN_CONFIG_ROOT,
        )
        self.assertEqual(owned["family_id"], "token_economics_configuration")
        self.assertFalse(runtime["candidate_commit_allowed"])

    def test_prefix_collisions_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_root = Path(temp_dir) / "token_economics"
            shutil.copytree(TOKEN_CONFIG_ROOT, config_root)
            registry_path = config_root / "artifact_ownership_registry.json"
            payload = json.loads(registry_path.read_text(encoding="utf-8"))
            payload["families"].append(
                {
                    "family_id": "overlap",
                    "logical_owner": "factory_platform_owner",
                    "producer": "test",
                    "artifact_kind": "configuration",
                    "candidate_commit_allowed": True,
                    "persistence_policy": "durable_repository_owned",
                    "stable_fields": ["schema_version"],
                    "volatile_fields": [],
                    "runtime_root": None,
                    "deterministic_contract": "exact_bytes",
                    "path_patterns": ["config/token_economics/governance_policy.json"],
                }
            )
            registry_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "multiple families"):
                resolve_artifact_owner(
                    "config/token_economics/governance_policy.json",
                    config_root=config_root,
                )

    def test_ledger_history_is_append_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ledger = LedgerStore(Path(temp_dir) / "ledger.jsonl")
            ledger.append({"provider_turn_id": "turn-1", "settlement": {"rounded_amount": "1.0000000"}})
            first_line = ledger.path.read_text(encoding="utf-8").splitlines()[0]
            ledger.append({"provider_turn_id": "turn-2", "settlement": {"rounded_amount": "2.0000000"}})
            lines = ledger.path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(lines[0], first_line)
            self.assertEqual(len(lines), 2)

    def test_governance_policy_preserves_scoped_budget_exceptions_and_legal_hold(self) -> None:
        policy = load_governance_policy(TOKEN_CONFIG_ROOT)
        self.assertIn("budget_exception", policy["decision_rights"]["human_authority"])
        self.assertTrue(policy["exception_policy"]["scoped"])
        self.assertTrue(policy["exception_policy"]["expiring"])
        self.assertTrue(policy["retention_policy"]["legal_hold_machine_readable"])

    def test_governance_policy_preserves_migration_compatibility(self) -> None:
        policy = load_governance_policy(TOKEN_CONFIG_ROOT)
        self.assertEqual(policy["compatibility_mappings"]["focus"], "compatibility_mapping_only")
        self.assertEqual(
            policy["compatibility_mappings"]["opentelemetry_genai"],
            "versioned_compatibility_adapter",
        )

    def test_rate_publication_and_certification_claims_stay_human_gated(self) -> None:
        policy = load_governance_policy(TOKEN_CONFIG_ROOT)
        rights = policy["decision_rights"]["human_authority"]
        self.assertIn("rate_card_publication", rights)
        self.assertIn("certification_claim", rights)


if __name__ == "__main__":
    unittest.main()
