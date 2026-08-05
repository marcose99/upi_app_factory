from __future__ import annotations

import asyncio
from pathlib import Path

import httpx

from factory.application_engineering.portfolio import PortfolioCatalogue, PortfolioStore
from factory.operator_portal.local_web_api import create_app
from scripts import run_portal_requirements_driven_application_engineering as adapter


ROOT = Path(__file__).resolve().parents[2]


async def _request(path: str) -> httpx.Response:
    app = create_app(project_root=ROOT)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://local-portal") as client:
        return await client.get(path)


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


def test_local_api_marks_runtime_routes_as_deprecated_compatibility_plane() -> None:
    authority = asyncio.run(_request("/operator-portal/api/runtime-plane-authority"))
    assert authority.status_code == 200
    payload = authority.json()
    assert payload["primary_runtime_plane"] == "portfolio_authoritative"
    assert (
        payload["compatibility_runtime_plane"]["status"]
        == "deprecated_compatibility_surface"
    )
    assert (
        payload["compatibility_runtime_plane"]["replacement_prefix"]
        == "/operator-portal/api/portfolio/runtime"
    )

    runtime_catalog = asyncio.run(_request("/operator-portal/api/runtime/scenario-catalog"))
    assert runtime_catalog.status_code == 200
    assert runtime_catalog.headers["deprecation"] == "true"
    assert runtime_catalog.headers["x-upi-runtime-plane"] == "runtime_compatibility_deprecated"
    assert runtime_catalog.headers["x-upi-runtime-plane-primary"] == "portfolio_authoritative"

    health = asyncio.run(_request("/operator-portal/health"))
    assert health.status_code == 200
    assert (
        health.json()["runtime_plane_authority"]["primary_runtime_plane"]
        == "portfolio_authoritative"
    )


def test_adapter_registration_publishes_authoritative_failed_debit_capabilities(
    tmp_path: Path,
) -> None:
    portfolio_root = tmp_path / "portfolio"
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
        factory_root=ROOT,
        workspace_root=tmp_path,
        portfolio_state_root=portfolio_root,
        engineering_profile="authoritative-failed-debit-v1",
        register_with_portfolio=True,
    )

    result = adapter.run(config)
    registration = result["portfolio_registration"]
    version = PortfolioCatalogue(
        store=PortfolioStore(project_root=ROOT, state_root=portfolio_root)
    ).get(
        app_id=registration["app_id"],
        version_id=registration["version_id"],
    )

    assert result["primary_runtime_control_plane"] == "portfolio_authoritative"
    assert "failed_debit_disputes" in version.capabilities
    assert "audit_integrity" in version.capabilities
    assert "closure" in version.capabilities
    assert "disputes" not in version.capabilities
