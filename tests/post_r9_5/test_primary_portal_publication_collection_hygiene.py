from __future__ import annotations

from pathlib import Path
import tempfile
import subprocess
import sys
import unittest

from scripts import run_portal_requirements_driven_application_engineering as adapter


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class PrimaryPortalPublicationCollectionHygieneTest(unittest.TestCase):
    def test_primary_portal_publication_ignores_wrapper_tests_during_repo_collection(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            publication_root = Path(temp_dir) / "publication"
            files = adapter._primary_runtime_wrapper_files(
                "upi_collection_safe",
                """# Primary portal failed-debit runtime

Deterministic local authoritative runtime wrapper.
""",
            )
            for relative_path, content in files.items():
                target = publication_root / relative_path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")

            nested_test = publication_root / "generated_application" / "app" / "tests" / "test_runtime_smoke.py"
            nested_test.parent.mkdir(parents=True, exist_ok=True)
            nested_test.write_text(
                "def test_runtime_smoke() -> None:\n    assert True\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [sys.executable, "-m", "pytest", "--collect-only", "-q", str(publication_root)],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            if completed.returncode != 0 and "No module named pytest" in completed.stderr:
                self.skipTest("pytest is not available in the local execution environment")

            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            self.assertNotIn("tests/test_api_contract.py", completed.stdout)
            self.assertNotIn("tests/test_service.py", completed.stdout)
            self.assertNotIn(adapter.PRIMARY_PORTAL_RUNTIME_TEST, completed.stdout)
            self.assertIn(
                "generated_application/app/tests/test_runtime_smoke.py::test_runtime_smoke",
                completed.stdout,
            )


if __name__ == "__main__":
    unittest.main()
