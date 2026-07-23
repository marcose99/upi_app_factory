from __future__ import annotations

from pathlib import Path
import shutil

import pytest
from fastapi.testclient import TestClient

from factory.application_engineering.portfolio import (
    LOCAL_APPROVAL_TOKEN,
    PortfolioCatalogue,
    PortfolioComparator,
    PortfolioError,
    PortfolioEvidenceService,
    PortfolioScenarioRunner,
    PortfolioStore,
    PortfolioSupervisor,
    QuotaContract,
    VersionState,
    approve_action,
    normalize_runtime_url,
)
from factory.operator_portal.local_web_api import create_app
from tests.phase51.conftest import (
    PROJECT_ROOT,
    free_port,
    mock_app,
    port_open,
    registration,
    wait_for_ports_closed,
)


PortfolioFixture = tuple[PortfolioStore, PortfolioCatalogue, PortfolioSupervisor, list[int]]


def _fresh_contained_test_root(tmp_path: Path, name: str) -> Path:
    root = PROJECT_ROOT / "workspace" / "factory_generated" / "phase51_portfolio_e2e_tests" / tmp_path.name / name
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    return root


def _portfolio_fixture(tmp_path: Path) -> PortfolioFixture:
    store = PortfolioStore(
        project_root=PROJECT_ROOT,
        state_root=_fresh_contained_test_root(tmp_path, "phase51_state"),
    )
    catalogue = PortfolioCatalogue(store=store)
    supervisor = PortfolioSupervisor(store=store, catalogue=catalogue)
    return store, catalogue, supervisor, []


def test_phase51_contracts_catalogue_lineage_and_fail_closed_security(
    tmp_path: Path,
) -> None:
    store, catalogue, _, _ = _portfolio_fixture(tmp_path)
    apps_root = _fresh_contained_test_root(tmp_path, "apps")
    app_root = mock_app(apps_root, "contracts_app", "v1")

    version = catalogue.register(
        registration(
            app_id="contracts_app",
            version_id="v1",
            generated_run_id="contracts_run_001",
            app_root=app_root,
            requirements="stable mock contracts",
            source_commit="abc123",
            manifest={"openapi": {"paths": {"/health": {}, "/scenario/echo": {}}}},
            capabilities=("echo",),
        )
    )

    assert version.identity_sha256
    assert version.requirements_digest
    assert version.evidence_checksum
    assert version.policy.mock_only is True
    assert version.policy.certification_posture == "certification-ready-not-certified"
    assert catalogue.catalogue()["catalogue_sha256"]

    superseding = catalogue.register(
        registration(
            app_id="contracts_app",
            version_id="v2",
            generated_run_id="contracts_run_002",
            app_root=mock_app(apps_root, "contracts_app_v2", "v2"),
            requirements="stable mock contracts v2",
            source_commit="def456",
            manifest={
                "openapi": {"paths": {"/health": {}, "/scenario/echo": {}, "/capabilities": {}}}
            },
            capabilities=("echo",),
        )
    )
    assert superseding.state == VersionState.ACTIVE
    assert catalogue.get(app_id="contracts_app", version_id="v1").state == VersionState.SUPERSEDED

    with pytest.raises(PortfolioError, match="invalid version transition"):
        catalogue.transition_version(
            app_id="contracts_app",
            version_id="v1",
            target=VersionState.ACTIVE,
        )
    with pytest.raises(PortfolioError, match="path traversal"):
        store.runtime_dir("../escape")
    with pytest.raises(PortfolioError, match="arbitrary filesystem"):
        catalogue.register(
            registration(
                app_id="bad_app",
                version_id="v1",
                generated_run_id="bad_run_001",
                app_root=Path("/"),
                requirements="bad",
                source_commit="bad",
                manifest={},
                capabilities=("echo",),
            )
        )

    catalogue_path = store.catalogue_path
    tampered = catalogue_path.read_text(encoding="utf-8").replace(
        "contracts_app",
        "tampered_app",
        1,
    )
    catalogue_path.write_text(tampered, encoding="utf-8")
    with pytest.raises(PortfolioError, match="tampering"):
        catalogue.catalogue()


def test_phase51_runtime_quotas_scenarios_comparison_and_evidence(
    tmp_path: Path,
) -> None:
    store, catalogue, supervisor, ports = _portfolio_fixture(tmp_path)
    apps_root = _fresh_contained_test_root(tmp_path, "apps")
    app_one = catalogue.register(
        registration(
            app_id="portfolio_alpha",
            version_id="v1",
            generated_run_id="alpha_run_001",
            app_root=mock_app(apps_root, "portfolio_alpha_v1", "alpha-v1"),
            requirements="alpha requirements",
            source_commit="1111111",
            manifest={"openapi": {"paths": {"/health": {}, "/scenario/echo": {}}}},
            capabilities=("echo",),
            quota=QuotaContract(max_concurrent_runtimes=2, max_restarts=1),
        )
    )
    app_two = catalogue.register(
        registration(
            app_id="portfolio_beta",
            version_id="v1",
            generated_run_id="beta_run_001",
            app_root=mock_app(apps_root, "portfolio_beta_v1", "beta-v1"),
            requirements="beta requirements",
            source_commit="2222222",
            manifest={
                "openapi": {"paths": {"/health": {}, "/scenario/echo": {}, "/capabilities": {}}}
            },
            capabilities=("echo",),
            quota=QuotaContract(max_concurrent_runtimes=2, max_restarts=1),
        )
    )
    port_one = free_port()
    port_two = free_port()
    ports.extend([port_one, port_two])

    first = supervisor.start(
        app_id=app_one.app_id,
        version_id=app_one.version_id,
        run_id="alpha_runtime_001",
        port=port_one,
    )
    second = supervisor.start(
        app_id=app_two.app_id,
        version_id=app_two.version_id,
        run_id="beta_runtime_001",
        port=port_two,
    )
    assert first.state.value == "READY"
    assert second.state.value == "READY"
    assert first.binding.host == "127.0.0.1"
    assert first.process is not None and second.process is not None

    with pytest.raises(PortfolioError, match="port"):
        supervisor.start(
            app_id=app_one.app_id,
            version_id=app_one.version_id,
            run_id="alpha_runtime_002",
            port=port_two,
        )

    scenario_runner = PortfolioScenarioRunner(store=store)
    first_results = scenario_runner.run_for_status(first)
    aggregate = scenario_runner.run_portfolio([first, second], parallel=True)
    assert first_results["decision"] == "GO"
    assert aggregate["decision"] == "GO"
    assert {item["category"] for item in first_results["results"]} >= {
        "positive",
        "negative",
        "boundary",
        "replay",
        "timeout",
        "security",
    }

    comparison = PortfolioComparator().compare(
        app_one,
        app_two,
        left_scenarios=first_results,
        right_scenarios=aggregate["applications"][1],
    )
    assert comparison["promotion_recommendation"]["production_deployment"] == "not_allowed"
    assert comparison["rollback_plan"]["type"] == "non_destructive"
    assert "/capabilities" in comparison["openapi_changes"]["added_paths"]

    evidence = PortfolioEvidenceService(store=store).manifest()
    assert evidence["decision"] == "GO"
    assert evidence["validation_gates"]["approval_plaintext_absent"] is True

    stopped = supervisor.stop_all()
    assert stopped["count"] >= 2
    assert not port_open(port_one)
    assert not port_open(port_two)


def test_phase51_portal_apis_ui_approvals_and_replay(tmp_path: Path) -> None:
    state_root = _fresh_contained_test_root(tmp_path, "portal_state")
    apps_root = _fresh_contained_test_root(tmp_path, "apps")
    store = PortfolioStore(project_root=PROJECT_ROOT, state_root=state_root)
    catalogue = PortfolioCatalogue(store=store)
    version = catalogue.register(
        registration(
            app_id="portal_alpha",
            version_id="v1",
            generated_run_id="portal_run_001",
            app_root=mock_app(apps_root, "portal_alpha_v1", "portal-v1"),
            requirements="portal requirements",
            source_commit="3333333",
            manifest={"openapi": {"paths": {"/health": {}, "/scenario/echo": {}}}},
            capabilities=("echo",),
        )
    )
    port = free_port()
    app = create_app(
        project_root=PROJECT_ROOT,
        runtime_state_root=_fresh_contained_test_root(tmp_path, "phase50"),
        portfolio_state_root=state_root,
    )
    client = TestClient(app)
    try:
        catalogue_response = client.get("/operator-portal/api/portfolio/catalogue")
        assert catalogue_response.status_code == 200
        assert catalogue_response.json()["mock_only"] is True

        openapi_response = client.post(
            "/operator-portal/api/portfolio/runtime/openapi",
            json={
                "app_id": version.app_id,
                "version_id": version.version_id,
            },
        )
        assert openapi_response.status_code == 200
        openapi_payload = openapi_response.json()
        assert openapi_payload["status"] == "available"
        assert openapi_payload["app_id"] == version.app_id
        assert openapi_payload["version_id"] == version.version_id
        assert openapi_payload["version_identity_sha256"] == version.identity_sha256
        assert openapi_payload["endpoint_inventory"] == [
            "/health",
            "/scenario/echo",
        ]
        assert openapi_payload["method_inventory"] == {
            "/health": [],
            "/scenario/echo": [],
        }
        assert openapi_payload["openapi"] == version.manifest["openapi"]

        missing_openapi = client.post(
            "/operator-portal/api/portfolio/runtime/openapi",
            json={
                "app_id": version.app_id,
                "version_id": "missing",
            },
        )
        assert missing_openapi.status_code == 404
        assert missing_openapi.json()["detail"]["status"] == "rejected"

        approval = client.post(
            "/operator-portal/api/portfolio/approvals",
            json={
                "action": "start",
                "scope": "portal_runtime_001",
                "actor": "tester",
                "approval_token": LOCAL_APPROVAL_TOKEN,
                "nonce": "nonce_start_001",
            },
        )
        assert approval.status_code == 200
        start_payload = {
            "app_id": version.app_id,
            "version_id": version.version_id,
            "run_id": "portal_runtime_001",
            "port": port,
            "approval_nonce": "nonce_start_001",
        }
        start = client.post("/operator-portal/api/portfolio/runtime/start", json=start_payload)
        assert start.status_code == 202
        assert start.json()["state"] == "READY"

        replay = client.post("/operator-portal/api/portfolio/runtime/start", json=start_payload)
        assert replay.status_code == 403

        scenarios = client.post(
            "/operator-portal/api/portfolio/scenarios",
            json={
                "app_id": version.app_id,
                "version_id": version.version_id,
                "run_id": "portal_runtime_001",
                "port": port,
            },
        )
        assert scenarios.status_code == 200
        assert scenarios.json()["decision"] == "GO"

        ui = client.get("/operator-portal/api/portfolio/view")
        assert ui.status_code == 200
        for text in [
            "Governed Portfolio Operations",
            "Runtime Controls",
            "Local-only",
            "Compare Versions",
            "Evidence",
        ]:
            assert text in ui.text

        quarantine_approval = approve_action(
            store=store,
            action="quarantine",
            scope="portal_alpha:v1",
            actor="tester",
            token=LOCAL_APPROVAL_TOKEN,
            nonce="nonce_quarantine_001",
        )
        lifecycle = client.post(
            "/operator-portal/api/portfolio/lifecycle",
            json={
                "app_id": "portal_alpha",
                "version_id": "v1",
                "target_state": "quarantined",
                "approval_nonce": quarantine_approval["nonce"],
            },
        )
        assert lifecycle.status_code == 200
        assert lifecycle.json()["state"] == "quarantined"

        stop_approval = client.post(
            "/operator-portal/api/portfolio/approvals",
            json={
                "action": "stop_all",
                "scope": "portfolio",
                "actor": "tester",
                "approval_token": LOCAL_APPROVAL_TOKEN,
                "nonce": "nonce_stop_all_001",
            },
        )
        assert stop_approval.status_code == 200
        stopped = client.post(
            "/operator-portal/api/portfolio/runtime/stop-all",
            params={"approval_nonce": "nonce_stop_all_001"},
        )
        assert stopped.status_code == 202
    finally:
        PortfolioSupervisor(store=store, catalogue=catalogue).stop_all()
        wait_for_ports_closed([port])
        assert not port_open(port)


def test_phase51_resilience_and_ssrf_guards(
    tmp_path: Path,
) -> None:
    store, catalogue, supervisor, ports = _portfolio_fixture(tmp_path)
    apps_root = _fresh_contained_test_root(tmp_path, "apps")
    version = catalogue.register(
        registration(
            app_id="resilience_app",
            version_id="v1",
            generated_run_id="resilience_run_001",
            app_root=mock_app(apps_root, "resilience_v1", "resilience-v1"),
            requirements="resilience requirements",
            source_commit="4444444",
            manifest={"openapi": {"paths": {"/health": {}}}},
            capabilities=("echo",),
            quota=QuotaContract(max_concurrent_runtimes=1, max_restarts=0),
        )
    )
    port = free_port()
    ports.append(port)
    status = supervisor.start(
        app_id=version.app_id,
        version_id=version.version_id,
        run_id="resilience_runtime_001",
        port=port,
    )
    assert status.state.value == "READY"

    try:
        with pytest.raises(PortfolioError, match="concurrency"):
            supervisor.start(
                app_id=version.app_id,
                version_id=version.version_id,
                run_id="resilience_runtime_002",
                port=free_port(),
            )
        with pytest.raises(PortfolioError, match="restart quota"):
            supervisor.restart(
                app_id=version.app_id,
                version_id=version.version_id,
                run_id="resilience_runtime_001",
                port=port,
            )
        with pytest.raises(PortfolioError, match="loopback"):
            normalize_runtime_url(
                base_url="http://169.254.169.254:80",
                method="GET",
                endpoint="/health",
                owned_port=80,
            )
        with pytest.raises(PortfolioError, match="escaped"):
            normalize_runtime_url(
                base_url=f"http://127.0.0.1:{port}",
                method="GET",
                endpoint="http://127.0.0.1/health",
                owned_port=port,
            )

        original = store.status_path("resilience_runtime_001").read_text(encoding="utf-8")
        tampered = original.replace(version.identity_sha256, "0" * 64)
        store.status_path("resilience_runtime_001").write_text(tampered, encoding="utf-8")
        try:
            with pytest.raises(PortfolioError, match="stale ownership"):
                supervisor.status(
                    app_id=version.app_id,
                    version_id=version.version_id,
                    run_id="resilience_runtime_001",
                    port=port,
                )
        finally:
            store.status_path("resilience_runtime_001").write_text(original, encoding="utf-8")
    finally:
        supervisor.stop(
            app_id=version.app_id,
            version_id=version.version_id,
            run_id="resilience_runtime_001",
            port=port,
        )
        wait_for_ports_closed(ports)
        assert not port_open(port)
