from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from factory.native_capability_prerun.improvement_workflow import (
    AUTHORIZATION_PHRASE,
    ImprovementWorkflowConfig,
    run_factory_improvement_workflow,
)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FactoryImprovementWorkflowExecutionTest(unittest.TestCase):
    def test_workflow_builds_isolated_candidate_and_validation_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "factory_root"
            (root / "factory").mkdir(parents=True)
            (root / "config").mkdir()
            (root / "scripts").mkdir()
            (root / "tests").mkdir()
            (root / "factory" / "__init__.py").write_text("", encoding="utf-8")
            (root / "factory" / "example.py").write_text("VALUE = 1\n", encoding="utf-8")
            (root / "scripts" / "example.py").write_text("VALUE = 2\n", encoding="utf-8")
            (root / "tests" / "test_smoke.py").write_text("def test_smoke() -> None:\n    assert True\n", encoding="utf-8")

            requirements = root / "improvements.json"
            requirements.write_text(
                json.dumps(
                    {
                        "items": [
                            {
                                "id": "FAC-IMP-001",
                                "normative_requirement": "The workflow SHALL create an isolated candidate projection.",
                            },
                            {
                                "id": "FAC-IMP-002",
                                "normative_requirement": "The workflow SHALL emit bounded validation evidence.",
                            },
                        ]
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            improvement_sha = _sha256_file(requirements)
            output_root = root / "workflow_output"

            result = run_factory_improvement_workflow(
                ImprovementWorkflowConfig(
                    improvement_requirements=requirements,
                    improvement_sha256=improvement_sha,
                    output_root=output_root,
                    factory_root=root,
                    plan_only=False,
                    authorization=f"{AUTHORIZATION_PHRASE}:{improvement_sha}",
                )
            )

            self.assertEqual(result["status"], "AUTHORIZED_SOURCE_CHANGE_VALIDATED")
            self.assertTrue(result["source_change_authorized"])
            semantics = result["isolated_branch_worktree_semantics"]
            self.assertTrue(semantics["candidate_projection_created"])
            self.assertEqual(semantics["implementation_mode"], "path_bounded_shadow_workspace")
            isolated_root = Path(semantics["workspace_root"])
            self.assertTrue((isolated_root / "APPLIED_IMPROVEMENTS.json").is_file())
            self.assertTrue((isolated_root / "CANDIDATE_PROJECTION.json").is_file())
            self.assertGreaterEqual(result["bounded_repair_validation"]["repair_cycles_executed"], 2)
            self.assertGreaterEqual(result["bounded_repair_validation"]["validation_cycles_executed"], 2)
            self.assertTrue((output_root / "FACTORY_IMPROVEMENT_WORKFLOW_RESULT.json").is_file())
            self.assertTrue((output_root / "FACTORY_IMPROVEMENT_EXECUTION_PLAN.json").is_file())
            self.assertTrue((output_root / "FACTORY_IMPROVEMENT_EXECUTION_PLAN.md").is_file())
            self.assertTrue((output_root / "FACTORY_IMPROVEMENT_VALIDATION_REPORT.json").is_file())
            self.assertEqual(
                [report["status"] for report in result["validation_reports"]],
                ["PASSED", "PASSED"],
            )


if __name__ == "__main__":
    unittest.main()
