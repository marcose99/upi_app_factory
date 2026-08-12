from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from factory.generated_application_artifacts import (
    EVIDENCE_AUTHORITY,
    NO_GO_EVIDENCE_DECISION,
    REQUIRED_ARTIFACT_RELATIVE_PATHS,
    REJECTED_PROJECTION_SHA256,
    REQUIREMENTS_PDF_SHA256,
    REQUIREMENTS_SCHEMA,
    build_generated_application_artifact_payloads,
    materialize_generated_application_artifacts,
)


ROOT = Path(__file__).resolve().parents[2]
TRACKED_APPLICATION_ROOT = (
    ROOT / "workspace" / "factory_generated" / "upi_dispute_resolution" / "generated_application"
)


class ExactV2TraceabilityTest(unittest.TestCase):
    def test_materializer_reproduces_tracked_exact_v2_artifacts(self) -> None:
        payloads = build_generated_application_artifact_payloads(ROOT)
        self.assertEqual(set(payloads), set(REQUIRED_ARTIFACT_RELATIVE_PATHS))
        self.assertIn("evidence/generation_summary.json", payloads)

        with tempfile.TemporaryDirectory() as temp_dir:
            application_root = Path(temp_dir) / "generated_application"
            result = materialize_generated_application_artifacts(
                ROOT,
                application_root=application_root,
            )

            self.assertEqual(result["status"], "MATERIALIZED")
            self.assertEqual(result["requirements_schema"], REQUIREMENTS_SCHEMA)
            self.assertEqual(result["supplied_pdf_sha256"], REQUIREMENTS_PDF_SHA256)
            self.assertEqual(result["rejected_projection_sha256"], REJECTED_PROJECTION_SHA256)
            self.assertEqual(result["exact_v2_evidence_decision"], NO_GO_EVIDENCE_DECISION)
            self.assertEqual(result["exact_v2_evidence_authority"], EVIDENCE_AUTHORITY)
            self.assertIs(result["exact_v2_mandatory_gate_passed"], False)

            matrix = json.loads(
                (application_root / "evidence" / "requirements_traceability_matrix.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(matrix["requirements_schema"], REQUIREMENTS_SCHEMA)
            self.assertEqual(matrix["supplied_pdf_sha256"], REQUIREMENTS_PDF_SHA256)
            self.assertEqual(matrix["rejected_projection_sha256"], REJECTED_PROJECTION_SHA256)
            status_count = (
                matrix["supported_obligation_count"]
                + matrix["partial_obligation_count"]
                + matrix["unsupported_obligation_count"]
                + sum(
                    item["support_status"]
                    == "NOT_APPLICABLE_WITH_JUSTIFICATION"
                    for item in matrix["items"]
                )
            )
            self.assertEqual(status_count, len(matrix["items"]))
            self.assertGreater(matrix["partial_obligation_count"], 0)
            self.assertEqual(matrix["evidence_authority"], EVIDENCE_AUTHORITY)
            self.assertIs(matrix["publication_authority"], True)
            self.assertIs(matrix["diagnostic_projection_used"], False)

            for item in matrix["items"]:
                self.assertIn("support_binding", item)
                if item["support_status"] == "SUPPORTED":
                    self.assertIsInstance(item["support_binding"], dict)
                else:
                    self.assertIsNone(item["support_binding"])
                for implementation_ref in item["implementation_refs"]:
                    self.assertTrue((ROOT / implementation_ref["path"]).is_file())

            for relative_path in REQUIRED_ARTIFACT_RELATIVE_PATHS:
                regenerated = (application_root / relative_path).read_text(encoding="utf-8")
                tracked = (TRACKED_APPLICATION_ROOT / relative_path).read_text(encoding="utf-8")
                self.assertEqual(regenerated, tracked, relative_path)


if __name__ == "__main__":
    unittest.main()
