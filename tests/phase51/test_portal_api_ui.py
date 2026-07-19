from __future__ import annotations

import json
from pathlib import Path
import time

from fastapi.testclient import TestClient

from factory.application_engineering.portfolio import (
    LOCAL_APPROVAL_TOKEN,
    PortfolioError,
    PortfolioCatalogue,
    PortfolioScenarioRunner,
    PortfolioStore,
    PortfolioSupervisor,
)
from factory.operator_portal.browser_intake_orchestration import (
    APPROVAL_TOKEN,
    BrowserIntakeOrchestrator,
)
from factory.operator_portal.local_web_api import create_app
from factory.operator_portal.portfolio_api import render_portfolio_view
from factory.operator_portal.web_ui import create_web_ui_app
from tests.phase51.conftest import (
    PROJECT_ROOT,
    free_port,
    mock_app,
    port_open,
    registration,
    wait_for_ports_closed,
)


def test_portfolio_catalogue_bootstraps_valid_empty_state(tmp_path: Path) -> None:
    state_root = tmp_path / "fresh_portfolio_state"
    app = create_app(project_root=PROJECT_ROOT, portfolio_state_root=state_root)
    client = TestClient(app)

    response = client.get("/operator-portal/api/portfolio/catalogue")

    assert response.status_code == 200
    payload = response.json()
    assert payload["versions"] == []
    assert payload["catalogue"]["versions"] == {}
    assert payload["catalogue"]["bootstrap_state"] == "empty_catalogue"
    assert payload["catalogue"]["catalogue_sha256"]
    assert (state_root / "portfolio_catalogue.json").is_file()


def test_portfolio_registration_replays_identical_immutable_version(
    tmp_path: Path,
) -> None:
    store = PortfolioStore(project_root=PROJECT_ROOT, state_root=tmp_path / "portfolio")
    catalogue = PortfolioCatalogue(store=store)
    request = registration(
        app_id="replay_app",
        version_id="v1_replay",
        generated_run_id="replay_run_001",
        app_root=mock_app(tmp_path, "replay_app", "replay"),
    )

    first = catalogue.register(request)
    second = catalogue.register(request)

    assert second.version_key == first.version_key
    assert second.identity_sha256 == first.identity_sha256
    assert len(catalogue.list_versions()) == 1


def test_portfolio_registration_rejects_same_id_different_content(
    tmp_path: Path,
) -> None:
    store = PortfolioStore(project_root=PROJECT_ROOT, state_root=tmp_path / "portfolio")
    catalogue = PortfolioCatalogue(store=store)
    app_root = mock_app(tmp_path, "collision_app", "collision")
    catalogue.register(
        registration(
            app_id="collision_app",
            version_id="v1_collision",
            generated_run_id="collision_run_001",
            app_root=app_root,
        )
    )

    try:
        catalogue.register(
            registration(
                app_id="collision_app",
                version_id="v1_collision",
                generated_run_id="collision_run_001",
                app_root=app_root,
                requirements="phase51 different immutable requirements",
            )
        )
    except PortfolioError as exc:
        assert "version id collision" in str(exc)
    else:
        raise AssertionError("same version id with different immutable content was accepted")


def test_browser_generation_registers_portfolio_version_and_metadata(tmp_path: Path) -> None:
    browser_root = tmp_path / "browser_runs"
    portfolio_root = tmp_path / "portfolio_state"
    orchestrator = BrowserIntakeOrchestrator(
        project_root=PROJECT_ROOT,
        state_root=browser_root,
        portfolio_state_root=portfolio_root,
    )
    requirements = (
        "Build a local mock-safe UPI failed debit dispute application with health, "
        "readiness, idempotent dispute intake, deterministic evidence, no live "
        "provider calls, no secrets, and certification-ready-not-certified posture."
    )

    run = orchestrator.create_run(requirements)
    run_id = str(run["run_id"])
    orchestrator.plan(run_id)
    orchestrator.approve(run_id, actor="tester", approval_token=APPROVAL_TOKEN)
    orchestrator.execute(run_id)
    deadline = time.monotonic() + 10
    completed = orchestrator.get_run(run_id)
    while completed["state"] not in {"SUCCEEDED", "FAILED", "CANCELLED"} and time.monotonic() < deadline:
        time.sleep(0.05)
        completed = orchestrator.get_run(run_id)

    assert completed["state"] == "SUCCEEDED"
    registration = completed["engineering_result"]["portfolio_registration"]
    assert registration["app_id"] == "upi_dispute_resolution"
    assert registration["version_id"].startswith("v1_")
    assert registration["source_run_id"] == run_id
    assert registration["requirements_sha256"] == completed["requirements_sha256"]
    assert Path(registration["application_root"]) == browser_root / run_id / "generated_application"
    assert Path(registration["catalogue_path"]) == portfolio_root / "portfolio_catalogue.json"

    metadata = json.loads(
        (browser_root / run_id / "generated_application" / "generation_metadata.json").read_text(
            encoding="utf-8"
        )
    )
    assert metadata["version_id"] == registration["version_id"]
    assert metadata["portfolio_registration"]["catalogue_sha256"] == registration["catalogue_sha256"]

    catalogue = PortfolioCatalogue(
        store=PortfolioStore(project_root=PROJECT_ROOT, state_root=portfolio_root)
    )
    version = catalogue.get(
        app_id=registration["app_id"],
        version_id=registration["version_id"],
    )
    assert version.generated_run_id == run_id
    assert version.application_root == str(browser_root / run_id / "generated_application")
    assert set(version.capabilities) >= {"echo", "health"}

    port = free_port()
    supervisor = PortfolioSupervisor(store=catalogue.store, catalogue=catalogue)
    try:
        status = supervisor.start(
            app_id=registration["app_id"],
            version_id=registration["version_id"],
            run_id="generated_runtime_001",
            port=port,
        )
        scenario_result = PortfolioScenarioRunner(store=catalogue.store).run_for_status(status)
        assert scenario_result["decision"] == "GO"
        assert {item["category"] for item in scenario_result["results"]} >= {
            "positive",
            "negative",
            "boundary",
            "replay",
            "timeout",
            "security",
        }
    finally:
        supervisor.stop_all()
        wait_for_ports_closed([port])


def test_portal_api_exposes_catalogue_runtime_scenarios_and_html_view(tmp_path: Path) -> None:
    state_root = tmp_path / "portal_state"
    store = PortfolioStore(project_root=PROJECT_ROOT, state_root=state_root)
    catalogue = PortfolioCatalogue(store=store)
    version = catalogue.register(
        registration(
            app_id="portal_api_app",
            app_root=mock_app(tmp_path, "portal_api_app", "portal"),
        )
    )
    port = free_port()
    app = create_app(
        project_root=PROJECT_ROOT,
        runtime_state_root=tmp_path / "phase50",
        portfolio_state_root=state_root,
    )
    client = TestClient(app)
    try:
        catalogue_payload = client.get("/operator-portal/api/portfolio/catalogue").json()
        assert catalogue_payload["versions"][0]["app_id"] == "portal_api_app"
        approval = client.post(
            "/operator-portal/api/portfolio/approvals",
            json={
                "action": "start",
                "scope": "portal_api_runtime_001",
                "actor": "tester",
                "approval_token": LOCAL_APPROVAL_TOKEN,
                "nonce": "nonce_portal_start",
            },
        )
        assert approval.status_code == 200
        start = client.post(
            "/operator-portal/api/portfolio/runtime/start",
            json={
                "app_id": version.app_id,
                "version_id": version.version_id,
                "run_id": "portal_api_runtime_001",
                "port": port,
                "approval_nonce": "nonce_portal_start",
            },
        )
        assert start.status_code == 202
        assert start.json()["state"] == "READY"
        scenarios = client.post(
            "/operator-portal/api/portfolio/scenarios",
            json={
                "app_id": version.app_id,
                "version_id": version.version_id,
                "run_id": "portal_api_runtime_001",
                "port": port,
            },
        )
        assert scenarios.json()["decision"] == "GO"
        view = client.get("/operator-portal/api/portfolio/view")
        assert "Governed Portfolio Operations" in view.text
        assert "portal_api_app" in view.text
    finally:
        PortfolioSupervisor(store=store, catalogue=catalogue).stop_all()
        wait_for_ports_closed([port])
        assert not port_open(port)


def test_rendered_portfolio_ui_escapes_catalogue_and_runtime_fields() -> None:
    html = render_portfolio_view(
        {
            "versions": [
                {
                    "app_id": "<script>alert(1)</script>",
                    "version_id": "v1",
                    "state": "active",
                    "generated_run_id": "run_001",
                    "evidence_checksum": "<b>checksum</b>",
                }
            ]
        },
        [
            {
                "binding": {
                    "run_id": "runtime_001",
                    "app_id": "safe_app",
                    "version_id": "v1",
                    "host": "127.0.0.1",
                    "port": 18051,
                },
                "state": "READY",
            }
        ],
    )

    assert "<script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "&lt;b&gt;checksum&lt;/b&gt;" in html


def test_runtime_operations_ui_uses_catalogue_backed_identity_selector() -> None:
    html = (PROJECT_ROOT / "factory/operator_portal/web_ui/static/index.html").read_text(
        encoding="utf-8"
    )
    js = (PROJECT_ROOT / "factory/operator_portal/web_ui/static/app.js").read_text(
        encoding="utf-8"
    )

    assert 'id="runtime-version-selector"' in html
    assert "Registered application/version" in html
    assert 'data-field="runtime-selected-app"' in html
    assert 'data-field="runtime-selected-version"' in html
    assert 'id="runtime-run-id"' in html
    assert 'id="runtime-port-input"' in html
    assert 'id="runtime-approve-restart-button"' in html
    assert 'data-action="runtime-restart"' in html
    assert 'id="runtime-approve-stop-all-button"' in html
    assert 'data-action="runtime-stop-all"' in html
    assert "/operator-portal/api/portfolio/catalogue" in js
    assert "/operator-portal/api/portfolio/runtime/start" in js
    assert "/operator-portal/api/portfolio/runtime/restart" in js
    assert "/operator-portal/api/portfolio/runtime/stop-all" in js
    assert "/operator-portal/api/portfolio/scenarios" in js
    assert "/operator-portal/api/portfolio/evidence" in js
    assert "/operator-portal/api/runtime/runs/" not in js


def test_portal_mounted_routes_cover_docs_and_deep_engineering_reads(tmp_path: Path) -> None:
    app = create_app(project_root=PROJECT_ROOT, portfolio_state_root=tmp_path / "portfolio")
    client = TestClient(app)

    docs = client.get("/docs")
    assert docs.status_code == 200
    assert "swagger" in docs.text.lower()

    redirect = client.get("/docs/oauth2-redirect")
    assert redirect.status_code == 200
    assert "oauth2" in redirect.text.lower()

    overview = client.get("/operator-portal/api/deep-engineering/overview")
    assert overview.status_code == 200
    assert overview.json()["schema_version"] == "phase58-deep-portal-overview.v1"
    assert overview.json()["mock_boundaries"]["live_provider_calls_allowed"] is False

    evidence = client.get(
        "/operator-portal/api/deep-engineering/evidence",
        params={"path": "generation_manifest.json"},
    )
    assert evidence.status_code in {200, 404}
    if evidence.status_code == 200:
        assert evidence.json()["path"] == "generation_manifest.json"


def test_portal_mounted_runtime_routes_are_mock_safe_and_guarded(tmp_path: Path) -> None:
    app = create_app(
        project_root=PROJECT_ROOT,
        runtime_state_root=tmp_path / "runtime_state",
        portfolio_state_root=tmp_path / "portfolio_state",
    )
    client = TestClient(app)
    run_id = "phase51_runtime_routes_001"

    status = client.get(f"/operator-portal/api/runtime/runs/{run_id}/status")
    assert status.status_code == 200
    assert status.json()["state"] == "ABSENT"

    logs = client.get(f"/operator-portal/api/runtime/runs/{run_id}/logs")
    assert logs.status_code == 200
    assert logs.json() == {"status": "missing", "run_id": run_id, "logs": ""}

    metrics = client.get(f"/operator-portal/api/runtime/runs/{run_id}/metrics")
    assert metrics.status_code == 200
    assert metrics.json()["mock_safe_local"] is True
    assert metrics.json()["real_payment_calls"] == "disabled"

    view = client.get(f"/operator-portal/api/runtime/runs/{run_id}/view")
    assert view.status_code == 200
    assert "Runtime Operations" in view.text

    catalog = client.get("/operator-portal/api/runtime/scenario-catalog")
    assert catalog.status_code == 200
    assert {"positive", "negative", "boundary", "idempotency", "resilience", "timeout", "security"}.issubset(
        set(catalog.json()["categories"])
    )

    evidence = client.get(f"/operator-portal/api/runtime/runs/{run_id}/evidence")
    assert evidence.status_code == 200
    assert evidence.json()["real_payment_calls"] == "disabled"
    assert evidence.json()["validation_gates"]["real_payment_calls_disabled"] is True

    guarded_start = client.post(
        f"/operator-portal/api/runtime/runs/{run_id}/start",
        json={"approval_nonce": "missing_nonce", "port": free_port()},
    )
    assert guarded_start.status_code == 403

    guarded_restart = client.post(
        f"/operator-portal/api/runtime/runs/{run_id}/restart",
        json={"approval_nonce": "missing_nonce", "port": free_port()},
    )
    assert guarded_restart.status_code == 403

    guarded_scenarios = client.post(
        f"/operator-portal/api/runtime/runs/{run_id}/scenarios",
        json={"port": free_port()},
    )
    assert guarded_scenarios.status_code == 409

    guarded_openapi = client.get(
        f"/operator-portal/api/runtime/runs/{run_id}/openapi",
        params={"port": free_port()},
    )
    assert guarded_openapi.status_code == 409


def test_runtime_operations_browser_smoke_uses_catalogue_identity_and_runtime_controls(
    tmp_path: Path,
) -> None:
    state_root = tmp_path / "portal_state"
    store = PortfolioStore(project_root=PROJECT_ROOT, state_root=state_root)
    catalogue = PortfolioCatalogue(store=store)
    version = catalogue.register(
        registration(
            app_id="browser_smoke_app",
            version_id="v1",
            generated_run_id="browser_smoke_run_001",
            app_root=mock_app(tmp_path, "browser_smoke_app", "browser-smoke"),
        )
    )
    api_app = create_app(
        project_root=PROJECT_ROOT,
        runtime_state_root=tmp_path / "runtime_state",
        portfolio_state_root=state_root,
    )
    api_client = TestClient(api_app)
    ui_client = TestClient(create_web_ui_app(project_root=PROJECT_ROOT))

    index = ui_client.get("/operator-ui/")
    assert index.status_code == 200
    for marker in [
        "runtime-version-selector",
        "runtime-approve-start",
        "runtime-start",
        "runtime-approve-restart",
        "runtime-restart",
        "runtime-scenarios",
        "runtime-approve-stop",
        "runtime-stop",
        "runtime-approve-stop-all",
        "runtime-stop-all",
        "runtime-evidence",
    ]:
        assert marker in index.text

    script = ui_client.get("/operator-ui/app.js")
    assert script.status_code == 200
    for endpoint in [
        "/operator-portal/api/portfolio/catalogue",
        "/operator-portal/api/portfolio/runtime/start",
        "/operator-portal/api/portfolio/runtime/restart",
        "/operator-portal/api/portfolio/runtime/stop",
        "/operator-portal/api/portfolio/runtime/stop-all",
        "/operator-portal/api/portfolio/scenarios",
        "/operator-portal/api/portfolio/evidence",
    ]:
        assert endpoint in script.text
    assert "window.localStorage.setItem(\"upi_app_factory_runtime_selection\"" in script.text

    payload = api_client.get("/operator-portal/api/portfolio/catalogue").json()
    assert payload["versions"][0]["app_id"] == version.app_id
    assert payload["versions"][0]["version_id"] == version.version_id

    replay = api_client.post(
        "/operator-portal/api/portfolio/runtime/start",
        json={
            "app_id": version.app_id,
            "version_id": version.version_id,
            "run_id": "browser_smoke_runtime_001",
            "port": free_port(),
            "approval_nonce": "missing_nonce",
        },
    )
    assert replay.status_code == 403
