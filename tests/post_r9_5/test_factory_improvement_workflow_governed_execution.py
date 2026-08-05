from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

from factory.native_capability_prerun.engine import GO_DECISION, sha256_file
from factory.native_capability_prerun.improvement_workflow import (
    AUTHORIZATION_PHRASE,
    ImprovementWorkflowConfig,
    run_factory_improvement_workflow,
)


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class GovernedFactoryImprovementWorkflowExecutionTest(unittest.TestCase):
    def test_governed_workflow_executes_bounded_repairs_in_disposable_repo(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "factory_root"
            _write_text(root / "factory" / "__init__.py", "")
            _write_text(
                root / "config" / "native_capability" / "catalogue.json",
                json.dumps(
                    {
                        "capabilities": [
                            {
                                "id": "CAP-DETERMINISTIC-REMEDIATION-EVIDENCE",
                                "description": "Repair proof exists only after the bounded fix materializes.",
                                "exact_texts": ["Deterministic remediation evidence SHALL exist"],
                                "evidence": [
                                    {"path": "factory/fixed_feature.py", "type": "implementation"},
                                    {"path": "tests/test_fixed_feature.py", "type": "unit_test"},
                                ],
                            }
                        ]
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
            )

            requirements_document = root / "requirements.md"
            requirements_document.write_text(
                "# Deterministic repair\n\nDeterministic remediation evidence SHALL exist.\n",
                encoding="utf-8",
            )
            requirements_sha = sha256_file(requirements_document)

            improvement_requirements = root / "improvements.json"
            improvement_requirements.write_text(
                json.dumps(
                    {
                        "requirements_sha256": requirements_sha,
                        "items": [
                            {
                                "id": "FAC-IMP-001",
                                "normative_requirement": (
                                    "The bounded remediation workflow SHALL materialize the missing "
                                    "implementation and test evidence inside an isolated disposable repository."
                                ),
                                "candidate_paths": ["factory/", "tests/"],
                            }
                        ],
                        "repair_actions": [
                            {
                                "id": "repair_factory_file",
                                "type": "write_text",
                                "path": "factory/fixed_feature.py",
                                "content": "VALUE = 7\n",
                            },
                            {
                                "id": "repair_test_file",
                                "type": "write_text",
                                "path": "tests/test_fixed_feature.py",
                                "content": (
                                    "from factory.fixed_feature import VALUE\n\n"
                                    "def test_fixed_feature() -> None:\n"
                                    "    assert VALUE == 7\n"
                                ),
                            },
                        ],
                        "validation_commands": {
                            "focused": [
                                [
                                    sys.executable,
                                    "-m",
                                    "unittest",
                                    "discover",
                                    "-s",
                                    "tests",
                                    "-p",
                                    "test_fixed_feature.py",
                                ]
                            ],
                            "full_regression": [[sys.executable, "-m", "unittest", "discover", "-s", "tests"]],
                        },
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            improvement_sha = hashlib.sha256(improvement_requirements.read_bytes()).hexdigest()

            output_root = root / "workflow_output"
            result = run_factory_improvement_workflow(
                ImprovementWorkflowConfig(
                    improvement_requirements=improvement_requirements,
                    improvement_sha256=improvement_sha,
                    output_root=output_root,
                    factory_root=root,
                    requirements_document=requirements_document,
                    application_id="demo_app",
                    plan_only=False,
                    authorization=f"{AUTHORIZATION_PHRASE}:{improvement_sha}",
                )
            )

            self.assertEqual(result["status"], "AUTHORIZED_SOURCE_CHANGE_VALIDATED")
            self.assertEqual(result["execution_mode"], "governed_execution")
            self.assertEqual(result["promotion_status"], "ELIGIBLE_NOT_PROMOTED")
            self.assertEqual(result["prohibited_actions_performed"], [])
            self.assertEqual(result["failure_reasons"], [])
            self.assertNotEqual(result["before_after_delta"]["before_decision"], GO_DECISION)
            self.assertEqual(result["before_after_delta"]["after_decision"], GO_DECISION)
            self.assertTrue(result["before_after_delta"]["capability_improved"])
            self.assertTrue(result["workflow_evidence_markers"]["full_regression"]["executed"])
            self.assertEqual(result["workflow_evidence_markers"]["full_regression"]["status"], "executed")
            self.assertTrue(result["workflow_evidence_markers"]["capability_re_evaluation"]["executed"])

            semantics = result["isolated_branch_worktree_semantics"]
            self.assertEqual(semantics["implementation_mode"], "isolated_disposable_git_repository")
            self.assertTrue(semantics["candidate_commit_created"])
            self.assertNotEqual(semantics["baseline_commit"], semantics["repair_commit"])

            isolated_root = Path(semantics["workspace_root"])
            self.assertTrue((isolated_root / ".git").is_dir())
            self.assertTrue((isolated_root / "factory" / "fixed_feature.py").is_file())
            self.assertTrue((isolated_root / "tests" / "test_fixed_feature.py").is_file())
            self.assertFalse((root / "factory" / "fixed_feature.py").exists())
            self.assertFalse((root / "tests" / "test_fixed_feature.py").exists())

            self.assertTrue(result["protected_action_audit"]["outer_repository_unchanged"])
            self.assertTrue((output_root / "FACTORY_IMPROVEMENT_CAPABILITY_DELTA.json").is_file())
            self.assertTrue((output_root / "FACTORY_IMPROVEMENT_PROTECTED_ACTION_AUDIT.json").is_file())
            self.assertEqual(
                [report["status"] for report in result["focused_validation_reports"]],
                ["PASSED"],
            )
            self.assertEqual(
                [report["status"] for report in result["full_regression_reports"]],
                ["PASSED"],
            )


if __name__ == "__main__":
    unittest.main()
