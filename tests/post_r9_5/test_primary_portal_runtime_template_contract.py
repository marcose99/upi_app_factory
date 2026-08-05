from __future__ import annotations

from pathlib import Path

from scripts import run_portal_requirements_driven_application_engineering as adapter


def test_primary_portal_runtime_template_emits_unescaped_runtime_fstrings(tmp_path: Path) -> None:
    requirements = tmp_path / "requirements.md"
    requirements.write_text(
        """# Primary portal failed-debit runtime

Build a deterministic local failed-debit runtime with mocked payment boundaries.
""",
        encoding="utf-8",
    )

    files = adapter._primary_runtime_wrapper_files(
        "upi_portal_template_contract",
        requirements.read_text(encoding="utf-8"),
    )
    primary_runtime_test = files[adapter.PRIMARY_PORTAL_RUNTIME_TEST]

    assert 'f"/v1/disputes/{dispute_id}/investigate"' in primary_runtime_test
    assert 'f"synthetic_{evidence_type}"' in primary_runtime_test
    assert 'f"portal-primary-evidence-{index}"' in primary_runtime_test
    assert "{{" not in primary_runtime_test
    assert "}}" not in primary_runtime_test
