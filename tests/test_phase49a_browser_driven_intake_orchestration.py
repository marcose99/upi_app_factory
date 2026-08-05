from __future__ import annotations

import asyncio
import hashlib
import io
import json
from pathlib import Path
import re
import time
import zipfile
from typing import Any, cast

import httpx
from fastapi import FastAPI

import factory.operator_portal.browser_intake_orchestration as orchestration
from factory.operator_portal.browser_intake_orchestration import (
    APPROVAL_TOKEN,
    BrowserIntakeOrchestrator,
)
from factory.operator_portal.local_web_api import create_app


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = PROJECT_ROOT / "factory/operator_portal/web_ui/static/index.html"
SCRIPT_PATH = PROJECT_ROOT / "factory/operator_portal/web_ui/static/app.js"


def requirements_text() -> str:
    return """# UPI dispute resolution requirements

Build a local mock-safe UPI dispute resolution API with health and readiness endpoints,
idempotent dispute creation, deterministic tests, evidence lineage, run-scoped downloads,
and no live payment provider calls.
"""


def make_app(tmp_path: Path) -> FastAPI:
    orchestrator = BrowserIntakeOrchestrator(
        project_root=PROJECT_ROOT,
        state_root=tmp_path / "portal_runs",
    )
    return create_app(project_root=PROJECT_ROOT, browser_orchestrator=orchestrator)


async def _request(
    app: FastAPI,
    method: str,
    path: str,
    *,
    json_payload: dict[str, Any] | None = None,
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://local-operator-portal") as client:
        return await client.request(method, path, json=json_payload)


def request(
    app: FastAPI,
    method: str,
    path: str,
    *,
    json_payload: dict[str, Any] | None = None,
) -> httpx.Response:
    return asyncio.run(_request(app, method, path, json_payload=json_payload))


def json_from_zip(archive: zipfile.ZipFile, name: str) -> dict[str, Any]:
    value = json.loads(archive.read(name).decode("utf-8"))
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


def test_source_commit_falls_back_when_git_executable_is_unavailable(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("UPI_APP_FACTORY_SOURCE_COMMIT", raising=False)

    def missing_git(*args: Any, **kwargs: Any) -> None:
        raise FileNotFoundError("git")

    monkeypatch.setattr(orchestration.subprocess, "run", missing_git)

    assert (
        orchestration._source_commit(tmp_path)
        == "unavailable:deterministic_non_git_non_manifest_source_root"
    )


def create_run(app: FastAPI) -> dict[str, Any]:
    response = request(
        app,
        "POST",
        "/operator-portal/api/runs",
        json_payload={"requirements": requirements_text()},
    )
    assert response.status_code == 201, response.text
    return cast(dict[str, Any], response.json())


def wait_for_terminal(app: FastAPI, run_id: str) -> dict[str, Any]:
    deadline = time.monotonic() + 30  # Bounded local evidence-generation allowance.
    while time.monotonic() < deadline:
        response = request(app, "GET", f"/operator-portal/api/runs/{run_id}")
        assert response.status_code == 200
        payload = response.json()
        if payload["state"] in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            return cast(dict[str, Any], payload)
        time.sleep(0.1)
    raise AssertionError("run did not reach a terminal state")


def test_browser_controls_exist_and_target_backend() -> None:
    html = INDEX_PATH.read_text(encoding="utf-8")
    script = SCRIPT_PATH.read_text(encoding="utf-8")
    for label in [
        "Validate Requirements",
        "Submit and Create Run",
        "Generate Plan",
        "Approve Application Engineering",
        "Start Engineering",
        "Cancel Run",
        "View Validation Report",
        "View Evidence",
        "Download Generated Application",
        "Download Evidence Bundle",
    ]:
        assert label in html
    for endpoint in [
        "/operator-portal/api/requirements/validate",
        "/operator-portal/api/runs",
        "/plan",
        "/approvals",
        "/execute",
        "/events",
        "/evidence",
        "/downloads/application",
        "/downloads/evidence",
    ]:
        assert endpoint in script


def test_valid_submit_returns_run_id_sha_and_governance(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    payload = create_run(app)
    assert payload["run_id"].startswith("run_")
    assert payload["requirements_sha256"] == hashlib.sha256(
        requirements_text().encode("utf-8")
    ).hexdigest()
    assert payload["approval_required"] is True
    assert payload["mock_boundary"] is True
    assert payload["real_payment_calls"] == "disabled"
    assert payload["llm_calls"] == 0
    assert payload["run"]["state"] == "REQUIREMENTS_ACCEPTED"


def test_invalid_input_and_secret_like_material_are_rejected(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    empty = request(
        app,
        "POST",
        "/operator-portal/api/requirements/validate",
        json_payload={"requirements": " \n\t "},
    )
    assert empty.status_code == 400
    assert empty.json()["detail"]["errors"][0]["code"] == "empty_requirements"

    secret = request(
        app,
        "POST",
        "/operator-portal/api/requirements/validate",
        json_payload={"requirements": requirements_text() + "\napi_key = 1234567890abcdef\n"},
    )
    assert secret.status_code == 400
    assert "secret_like_material" in secret.text
    assert "Traceback" not in secret.text


def test_run_persistence_is_run_scoped_and_blocks_path_traversal(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    payload = create_run(app)
    run_id = payload["run_id"]
    run_dir = tmp_path / "portal_runs" / run_id
    assert (run_dir / "requirements.md").read_text(encoding="utf-8") == requirements_text()
    assert json.loads((run_dir / "state.json").read_text(encoding="utf-8"))[
        "requirements_sha256"
    ] == payload["requirements_sha256"]

    traversal = request(app, "GET", "/operator-portal/api/runs/../AGENTS.md")
    assert traversal.status_code == 404


def test_plan_only_does_not_create_generated_application_and_invalid_transition_conflicts(
    tmp_path: Path,
) -> None:
    app = make_app(tmp_path)
    payload = create_run(app)
    run_id = payload["run_id"]

    plan = request(app, "POST", f"/operator-portal/api/runs/{run_id}/plan")
    assert plan.status_code == 200, plan.text
    run_dir = tmp_path / "portal_runs" / run_id
    assert (run_dir / "plan.json").is_file()
    assert not (run_dir / "generated_application").exists()

    cancelled = request(app, "POST", f"/operator-portal/api/runs/{run_id}/cancel")
    assert cancelled.status_code == 202
    terminal_plan = request(app, "POST", f"/operator-portal/api/runs/{run_id}/plan")
    assert terminal_plan.status_code == 409


def test_execute_without_approval_fails_closed_and_approval_is_run_scoped(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    first = create_run(app)["run_id"]
    second = create_run(app)["run_id"]
    assert request(app, "POST", f"/operator-portal/api/runs/{first}/plan").status_code == 200
    assert request(app, "POST", f"/operator-portal/api/runs/{second}/plan").status_code == 200

    blocked = request(app, "POST", f"/operator-portal/api/runs/{first}/execute")
    assert blocked.status_code == 409

    wrong_approval = request(
        app,
        "POST",
        f"/operator-portal/api/runs/{first}/approvals",
        json_payload={"actor": "operator-a", "approval_token": "wrong-token"},
    )
    assert wrong_approval.status_code == 403
    assert APPROVAL_TOKEN not in wrong_approval.text

    approval = request(
        app,
        "POST",
        f"/operator-portal/api/runs/{first}/approvals",
        json_payload={"actor": "operator-a", "approval_token": APPROVAL_TOKEN},
    )
    assert approval.status_code == 200
    assert approval.json()["run"]["approval"]["run_id"] == first
    assert "approval_token" not in json.dumps(approval.json())
    assert "approval_token_sha256" not in json.dumps(approval.json())

    other_blocked = request(app, "POST", f"/operator-portal/api/runs/{second}/execute")
    assert other_blocked.status_code == 409


def test_duplicate_execute_is_idempotent_while_queued(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    run_id = create_run(app)["run_id"]
    assert request(app, "POST", f"/operator-portal/api/runs/{run_id}/plan").status_code == 200
    assert (
        request(
            app,
            "POST",
            f"/operator-portal/api/runs/{run_id}/approvals",
            json_payload={"actor": "operator-a", "approval_token": APPROVAL_TOKEN},
        ).status_code
        == 200
    )
    first = request(app, "POST", f"/operator-portal/api/runs/{run_id}/execute")
    second = request(app, "POST", f"/operator-portal/api/runs/{run_id}/execute")
    assert first.status_code == 202
    assert second.status_code in {202, 409}


def test_successful_progress_events_downloads_and_checksums(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    run_id = create_run(app)["run_id"]
    assert request(app, "POST", f"/operator-portal/api/runs/{run_id}/plan").status_code == 200
    assert (
        request(
            app,
            "POST",
            f"/operator-portal/api/runs/{run_id}/approvals",
            json_payload={"actor": "operator-a", "approval_token": APPROVAL_TOKEN},
        ).status_code
        == 200
    )
    queued = request(app, "POST", f"/operator-portal/api/runs/{run_id}/execute")
    assert queued.status_code == 202
    assert queued.json()["status"] in {"queued", "already_queued"}

    run = wait_for_terminal(app, run_id)
    assert run["state"] == "SUCCEEDED"
    assert run["final_decision"] == "GO"
    assert run["artifacts"]["generated_application_available"] is True

    events = request(app, "GET", f"/operator-portal/api/runs/{run_id}/events")
    assert events.status_code == 200
    assert any(event["type"] == "state_transition" for event in events.json()["events"])

    evidence = request(app, "GET", f"/operator-portal/api/runs/{run_id}/evidence")
    assert evidence.status_code == 200
    evidence_payload = evidence.json()
    assert evidence_payload["mock_boundary"] is True
    assert evidence_payload["real_payment_calls"] == "disabled"
    assert evidence_payload["llm_calls"] == 0
    assert evidence_payload["quality_gates"]["health_contract"] is True

    validation = request(app, "GET", f"/operator-portal/api/runs/{run_id}/validation")
    assert validation.status_code == 200
    assert validation.json()["mandatory_gates_passed"] is True

    app_download = request(app, "GET", f"/operator-portal/api/runs/{run_id}/downloads/application")
    assert app_download.status_code == 200
    expected_requirements_sha = hashlib.sha256(requirements_text().encode("utf-8")).hexdigest()
    with zipfile.ZipFile(io.BytesIO(app_download.content)) as archive:
        names = archive.namelist()
        assert all(not name.endswith("/") for name in names)
        top_level = {name.split("/", 1)[0] for name in names}
        assert top_level == {"generated_application"}
        manifest_members = [
            name for name in names if name == "generated_application/generation_manifest.json"
        ]
        assert manifest_members == ["generated_application/generation_manifest.json"]
        manifest = json.loads(archive.read(manifest_members[0]).decode("utf-8"))
        assert {
            "schema_version",
            "artifact_type",
            "run_id",
            "app_id",
            "requirements_sha256",
            "generator_entrypoint",
            "generated_at_utc",
            "mock_boundary",
            "real_payment_calls",
            "default_runtime_llm_calls",
            "certification_posture",
            "files",
        } <= set(manifest)
        assert manifest["schema_version"] == "1.0"
        assert manifest["artifact_type"] == "generated_application"
        assert manifest["run_id"] == run_id
        assert manifest["app_id"] == "upi_dispute_resolution"
        if "version_id" in manifest:
            assert re.fullmatch(r"v[0-9][A-Za-z0-9_.-]{0,63}", manifest["version_id"])
        if "portfolio_registration" in manifest:
            assert manifest["portfolio_registration"]["app_id"] == manifest["app_id"]
        assert manifest["requirements_sha256"] == expected_requirements_sha
        assert re.fullmatch(r"[0-9a-f]{64}", manifest["requirements_sha256"])
        assert manifest["generator_entrypoint"] == (
            "scripts/run_portal_requirements_driven_application_engineering.py"
        )
        assert (PROJECT_ROOT / manifest["generator_entrypoint"]).is_file()
        assert re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z",
            manifest["generated_at_utc"],
        )
        assert manifest["mock_boundary"] == "enforced"
        assert manifest["real_payment_calls"] == "disabled"
        assert manifest["default_runtime_llm_calls"] == 0
        assert manifest["certification_posture"] == "certification-ready-not-certified"

        archived_application_paths = sorted(
            name.split("/", 1)[1]
            for name in names
            if name != "generated_application/generation_manifest.json"
        )
        inventory = manifest["files"]
        inventory_paths = [item["path"] for item in inventory]
        assert inventory_paths == sorted(inventory_paths)
        assert inventory_paths == archived_application_paths
        assert len(inventory_paths) == len(set(inventory_paths))
        assert "generation_manifest.json" not in inventory_paths
        assert all(not path.startswith("/") for path in inventory_paths)
        assert all(".." not in Path(path).parts for path in inventory_paths)

        for item in inventory:
            member = f"generated_application/{item['path']}"
            archived_bytes = archive.read(member)
            assert re.fullmatch(r"[0-9a-f]{64}", item["sha256"])
            assert item["sha256"] == hashlib.sha256(archived_bytes).hexdigest()
            assert item["size_bytes"] == len(archived_bytes)
            assert isinstance(item["size_bytes"], int)
            assert item["size_bytes"] >= 0

    evidence_download = request(app, "GET", f"/operator-portal/api/runs/{run_id}/downloads/evidence")
    assert evidence_download.status_code == 200
    assert (
        evidence_download.headers["content-disposition"]
        == f'attachment; filename="{run_id}_evidence_bundle.zip"'
    )
    archive_path = tmp_path / "evidence.zip"
    archive_path.write_bytes(evidence_download.content)
    with zipfile.ZipFile(archive_path) as archive:
        evidence_names = archive.namelist()
        assert all(not name.endswith("/") for name in evidence_names)
        top_level = {name.split("/", 1)[0] for name in evidence_names}
        assert top_level == {f"{run_id}_evidence"}
        evidence_paths = [name.split("/", 1)[1] for name in evidence_names]
        required_paths = {
            "requirements.md",
            "plan.json",
            "approval_ledger.json",
            "event_ledger.jsonl",
            "execution_report.json",
            "generated_test_execution.json",
            "openapi.json",
            "openapi_inventory.json",
            "validation_report.json",
            "decision.json",
            "application_archive.sha256",
            "evidence_manifest.json",
        }
        assert set(evidence_paths) == required_paths
        assert len(evidence_paths) == len(set(evidence_paths))
        assert all(not path.startswith("/") for path in evidence_paths)
        assert all(".." not in Path(path).parts for path in evidence_paths)
        assert all(info.external_attr >> 16 & 0o170000 != 0o120000 for info in archive.infolist())

        prefix = f"{run_id}_evidence/"
        requirements_bytes = archive.read(prefix + "requirements.md")
        assert requirements_bytes == requirements_text().encode("utf-8")
        requirements_sha = hashlib.sha256(requirements_bytes).hexdigest()
        assert requirements_sha == expected_requirements_sha

        plan = json_from_zip(archive, prefix + "plan.json")
        assert plan["schema_version"] == "1.0"
        assert plan["run_id"] == run_id
        assert plan["requirements_sha256"] == requirements_sha
        assert re.fullmatch(r"[0-9a-f]{64}", plan["plan_sha256"])
        assert plan["generator_entrypoint"] == (
            "scripts/run_portal_requirements_driven_application_engineering.py"
        )
        assert plan["mock_boundary"] == "enforced"
        assert plan["real_payment_calls"] == "disabled"
        assert plan["default_runtime_llm_calls"] == 0

        approval = json_from_zip(archive, prefix + "approval_ledger.json")
        assert approval == {
            "schema_version": "1.0",
            "run_id": run_id,
            "action": "APPLICATION_ENGINEERING",
            "approved": True,
            "requirements_sha256": requirements_sha,
            "plan_sha256": plan["plan_sha256"],
            "approved_at_utc": approval["approved_at_utc"],
        }
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", approval["approved_at_utc"])

        event_lines = archive.read(prefix + "event_ledger.jsonl").decode("utf-8").splitlines()
        assert event_lines
        event_records = [json.loads(line) for line in event_lines if line.strip()]
        sequences = [event["sequence"] for event in event_records]
        assert sequences == sorted(sequences)
        assert len(sequences) == len(set(sequences))
        for event in event_records:
            assert isinstance(event, dict)
            assert isinstance(event["sequence"], int)
            assert event["sequence"] > 0
            assert isinstance(event["event_type"], str) and event["event_type"]
            assert isinstance(event["state"], str) and event["state"]
            assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", event["recorded_at_utc"])
        assert any(event["state"] == "SUCCEEDED" for event in event_records)

        app_download_filename = re.search(
            r'filename="([^"]+)"',
            app_download.headers["content-disposition"],
        )
        assert app_download_filename is not None
        expected_app_sha = hashlib.sha256(app_download.content).hexdigest()
        application_sha_text = archive.read(prefix + "application_archive.sha256").decode("utf-8")
        assert application_sha_text == (
            f"{expected_app_sha}  {app_download_filename.group(1)}\n"
        )

        execution_report = json_from_zip(archive, prefix + "execution_report.json")
        generated_test_execution = json_from_zip(archive, prefix + "generated_test_execution.json")
        openapi_document = json_from_zip(archive, prefix + "openapi.json")
        openapi_inventory = json_from_zip(archive, prefix + "openapi_inventory.json")
        assert execution_report == {
            "schema_version": "1.0",
            "run_id": run_id,
            "state": "SUCCEEDED",
            "generator_entrypoint": "scripts/run_portal_requirements_driven_application_engineering.py",
            "application_archive_sha256": expected_app_sha,
            "application_archive_size_bytes": len(app_download.content),
            "generated_test_execution_sha256": hashlib.sha256(
                json.dumps(generated_test_execution, sort_keys=True).encode("utf-8")
            ).hexdigest(),
            "openapi_sha256": openapi_inventory["openapi_sha256"],
            "mock_boundary": "enforced",
            "real_payment_calls": "disabled",
            "default_runtime_llm_calls": 0,
            "completed_at_utc": execution_report["completed_at_utc"],
        }
        assert re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z",
            execution_report["completed_at_utc"],
        )
        assert generated_test_execution["exit_code"] == 0
        assert generated_test_execution["go_gate"] == "GO"
        assert generated_test_execution["counts"]["collected"] > 0
        assert openapi_document["openapi"].startswith("3.")
        assert "/health" in openapi_document["paths"]
        assert openapi_inventory["catalogue_only_fallback_used"] is False
        assert {"method": "GET", "path": "/health"} in openapi_inventory["endpoint_inventory"]

        validation_report = json_from_zip(archive, prefix + "validation_report.json")
        assert validation_report["schema_version"] == "1.0"
        assert validation_report["run_id"] == run_id
        assert validation_report["requirements_sha256"] == requirements_sha
        assert validation_report["passed"] is True
        assert validation_report["mandatory_gates_passed"] is True
        assert validation_report["failure_count"] == 0
        gates = validation_report["gates"]
        assert gates
        gate_names = {gate["name"] for gate in gates}
        assert {
            "generated application structure",
            "tests",
            "tests executed",
            "OpenAPI publication",
            "archive safety",
            "generation manifest",
            "mock boundary",
            "real payment calls disabled",
            "certification posture",
        }.issubset(gate_names)
        for gate in gates:
            assert gate["passed"] is True
            assert isinstance(gate["evidence"], str) and gate["evidence"]

        decision = json_from_zip(archive, prefix + "decision.json")
        assert decision["schema_version"] == "1.0"
        assert decision["run_id"] == run_id
        assert decision["requirements_sha256"] == requirements_sha
        assert decision["decision"] == "GO"
        assert decision["source"] == "validation"
        assert decision["certification_posture"] == "certification-ready-not-certified"
        assert decision["real_payment_calls"] == "disabled"
        assert decision["default_runtime_llm_calls"] == 0
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", decision["decided_at_utc"])

        evidence_manifest = json_from_zip(archive, prefix + "evidence_manifest.json")
        assert evidence_manifest["schema_version"] == "1.0"
        assert evidence_manifest["artifact_type"] == "run_evidence_bundle"
        assert evidence_manifest["run_id"] == run_id
        assert evidence_manifest["requirements_sha256"] == requirements_sha
        assert evidence_manifest["application_archive_sha256"] == expected_app_sha
        assert evidence_manifest["mock_boundary"] == "enforced"
        assert evidence_manifest["real_payment_calls"] == "disabled"
        assert evidence_manifest["default_runtime_llm_calls"] == 0
        assert evidence_manifest["certification_posture"] == "certification-ready-not-certified"
        assert re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z",
            evidence_manifest["generated_at_utc"],
        )
        inventory = evidence_manifest["files"]
        inventory_paths = [item["path"] for item in inventory]
        expected_inventory_paths = sorted(required_paths - {"evidence_manifest.json"})
        assert inventory_paths == expected_inventory_paths
        assert inventory_paths == sorted(inventory_paths)
        assert len(inventory_paths) == len(set(inventory_paths))
        for item in inventory:
            assert not item["path"].startswith("/")
            assert ".." not in Path(item["path"]).parts
            archived_bytes = archive.read(prefix + item["path"])
            assert item["sha256"] == hashlib.sha256(archived_bytes).hexdigest()
            assert item["size_bytes"] == len(archived_bytes)

        archive_bytes = b"".join(archive.read(name) for name in evidence_names)
        assert APPROVAL_TOKEN.encode("utf-8") not in archive_bytes
        assert hashlib.sha256(APPROVAL_TOKEN.encode("utf-8")).hexdigest().encode("utf-8") not in archive_bytes
        assert b"approval_subject_sha256" not in archive_bytes
        assert b"official_certification_granted" not in archive_bytes
        assert b"production_readiness_claimed" not in archive_bytes
        assert b"real_payment_calls\": \"enabled" not in archive_bytes


def test_configured_publication_root_supports_read_only_project_root(tmp_path: Path) -> None:
    publication_root = tmp_path / "writable_publications"
    orchestrator = BrowserIntakeOrchestrator(
        project_root=PROJECT_ROOT,
        state_root=tmp_path / "portal_runs",
        portfolio_state_root=tmp_path / "portfolio",
        publication_root=publication_root,
    )
    run_id = orchestrator.create_run(requirements_text())["run_id"]
    assert orchestrator.plan(run_id)["status"] == "plan_ready"
    assert (
        orchestrator.approve(
            run_id,
            actor="operator-a",
            approval_token=APPROVAL_TOKEN,
        )["status"]
        == "approved"
    )
    assert orchestrator.execute(run_id)["status"] in {"queued", "already_queued"}

    deadline = time.monotonic() + 30  # Bounded local evidence-generation allowance.
    terminal = orchestrator.get_run(run_id)
    while terminal["state"] not in {"SUCCEEDED", "FAILED", "CANCELLED"} and time.monotonic() < deadline:
        time.sleep(0.1)
        terminal = orchestrator.get_run(run_id)

    assert terminal["state"] == "SUCCEEDED"
    registration = terminal["engineering_result"]["portfolio_registration"]
    application_root = Path(registration["application_root"])
    assert application_root.is_relative_to(publication_root)
    assert not application_root.is_relative_to(PROJECT_ROOT)
    assert orchestrator.application_archive(run_id).is_file()


def test_downloads_are_unavailable_before_terminal_success(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    run_id = create_run(app)["run_id"]

    app_download = request(app, "GET", f"/operator-portal/api/runs/{run_id}/downloads/application")
    evidence_download = request(app, "GET", f"/operator-portal/api/runs/{run_id}/downloads/evidence")

    assert app_download.status_code == 409
    assert evidence_download.status_code == 409

    cancelled = request(app, "POST", f"/operator-portal/api/runs/{run_id}/cancel")
    assert cancelled.status_code == 202
    cancelled_evidence = request(app, "GET", f"/operator-portal/api/runs/{run_id}/downloads/evidence")
    assert cancelled_evidence.status_code == 409


def test_canonical_source_not_modified_by_runtime_flow(tmp_path: Path) -> None:
    source = PROJECT_ROOT / "scripts/run_portal_requirements_driven_application_engineering.py"
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    app = make_app(tmp_path)
    run_id = create_run(app)["run_id"]
    assert request(app, "POST", f"/operator-portal/api/runs/{run_id}/plan").status_code == 200
    after = hashlib.sha256(source.read_bytes()).hexdigest()
    assert after == before
