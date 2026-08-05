from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from scripts import run_portal_requirements_driven_application_engineering as adapter


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _requirements(tmp_path: Path) -> Path:
    path = tmp_path / "requirements.md"
    path.write_text(
        """# Primary portal failed-debit runtime

Build and register the authoritative local failed-debit runtime with evidence
collection, investigation, human review, disposition, audit verification,
closure, mock-only payment boundaries, and deterministic local test proof.
""",
        encoding="utf-8",
    )
    return path


def test_authoritative_profile_reports_echo_capability_for_portfolio_runtime_scenarios(
    tmp_path: Path,
) -> None:
    config = adapter.AdapterConfig(
        requirements=_requirements(tmp_path),
        app_id="upi_dispute_resolution",
        output_root=tmp_path / "generated_application",
        evidence_root=tmp_path / "engineering_evidence",
        approval_mode="human-gated",
        approval_token=adapter.APPROVAL_TOKEN,
        mock_safe=True,
        plan_only=False,
        replace_existing=False,
        factory_root=PROJECT_ROOT,
        workspace_root=tmp_path,
        engineering_profile="authoritative-failed-debit-v1",
        register_with_portfolio=False,
    )

    result = cast(dict[str, Any], adapter.run(config))

    assert result["status"] == adapter.SUCCESS_STATUS
    assert {"echo", "health", "ready"} <= set(cast(list[str], result["capabilities"]))
    endpoints = {
        (item["method"], item["path"])
        for item in cast(list[dict[str, str]], result["openapi_inventory"]["endpoint_inventory"])
    }
    assert ("POST", "/scenario/echo") in endpoints
