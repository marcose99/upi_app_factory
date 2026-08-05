from __future__ import annotations

import unittest
from pathlib import Path
import tempfile

from scripts import run_portal_requirements_driven_application_engineering as adapter


class PrimaryPortalNestedRuntimeHygieneTest(unittest.TestCase):
    def test_copy_strips_wrapper_tests_and_alias_from_nested_authoritative_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_root = root / "source"
            destination_root = root / "publication" / "generated_application"
            self._write(
                source_root / "app" / "interfaces" / "api" / "main.py",
                "from generated_application.app.interfaces.api.main import app\n",
            )
            self._write(
                source_root / "tests" / "test_api_contract.py",
                "def test_wrapper_openapi_exposes_authoritative_failed_debit_surface() -> None:\n    assert True\n",
            )
            self._write(
                source_root / "tests" / "test_service.py",
                "def test_wrapper_entrypoint_and_nested_runtime_assets_exist() -> None:\n    assert True\n",
            )
            self._write(
                source_root / "app" / "upi_dispute_resolution" / "interfaces" / "api" / "main.py",
                "from generated_application.app.interfaces.api.main import app\n\n__all__ = ['app']\n",
            )
            self._write(
                source_root / "tests" / "test_authoritative_runtime.py",
                "def test_authoritative_runtime() -> None:\n    assert True\n",
            )

            adapter._copy_authoritative_runtime_into_publication(
                source_root=source_root,
                destination_root=destination_root,
                app_id="upi_dispute_resolution",
            )

            self.assertTrue((destination_root / "app" / "interfaces" / "api" / "main.py").is_file())
            self.assertTrue((destination_root / "tests" / "test_authoritative_runtime.py").is_file())
            self.assertFalse((destination_root / "tests" / "test_api_contract.py").exists())
            self.assertFalse((destination_root / "tests" / "test_service.py").exists())
            self.assertFalse(
                (
                    destination_root
                    / "app"
                    / "upi_dispute_resolution"
                    / "interfaces"
                    / "api"
                    / "main.py"
                ).exists()
            )

    @staticmethod
    def _write(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
