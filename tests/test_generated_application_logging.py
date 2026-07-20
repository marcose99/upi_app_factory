from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from scripts import run_portal_requirements_driven_application_engineering as adapter


def test_generated_application_includes_parameterized_logging_contract(tmp_path: Path) -> None:
    requirements = tmp_path / "requirements.md"
    requirements.write_text(
        "Build a fictional local mock-safe UPI app with health, ready, tests, evidence, and no live payment calls.",
        encoding="utf-8",
    )
    app_id = "upi_fictional_demo"
    config = adapter.AdapterConfig(
        requirements=requirements,
        app_id=app_id,
        output_root=tmp_path / "out",
        evidence_root=tmp_path / "evidence",
        approval_mode="proposal-only",
        approval_token=None,
        mock_safe=True,
        plan_only=True,
        replace_existing=False,
        factory_root=Path(__file__).resolve().parents[1],
        workspace_root=tmp_path,
        portfolio_state_root=tmp_path / "portfolio",
    )
    files = cast(Any, adapter)._project_files(config, requirements.read_text(encoding="utf-8"), "a" * 64)
    main = files[f"app/{app_id}/interfaces/api/main.py"]
    logging_module = files[f"app/{app_id}/observability/structured_logging.py"]
    assert f'configure_logging(service_name="{app_id}"' in main
    assert "request_logging_middleware" in main
    assert "upi-app-factory.log.v1" in logging_module
    assert "traceparent" in logging_module
