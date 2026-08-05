from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from factory.generated_application_artifacts import (
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

            matrix = json.loads(
                (application_root / "evidence" / "requirements_traceability_matrix.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(matrix["requirements_schema"], REQUIREMENTS_SCHEMA)
            self.assertEqual(matrix["supplied_pdf_sha256"], REQUIREMENTS_PDF_SHA256)
            self.assertEqual(matrix["rejected_projection_sha256"], REJECTED_PROJECTION_SHA256)
            self.assertGreaterEqual(matrix["supported_obligation_count"], 6)

            for item in matrix["items"]:
                for implementation_ref in item["implementation_refs"]:
                    self.assertTrue((ROOT / implementation_ref["path"]).is_file())

            for relative_path in REQUIRED_ARTIFACT_RELATIVE_PATHS:
                regenerated = (application_root / relative_path).read_text(encoding="utf-8")
                tracked = (TRACKED_APPLICATION_ROOT / relative_path).read_text(encoding="utf-8")
                self.assertEqual(regenerated, tracked, relative_path)


if __name__ == "__main__":
    unittest.main()
