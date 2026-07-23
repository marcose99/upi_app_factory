from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_ID = "upi_failed_debit_no_credit"
APPROVAL_TOKEN = "APPROVE_PORTAL_APPLICATION_ENGINEERING"
REQUIREMENTS_TEXT = """# UPI Failed Debit - Beneficiary Not Credited

Requirement ID: upi_failed_debit_no_credit.requirements.v1.
Build a local deterministic mock-safe payment-operations case workflow for a
failed debit where the beneficiary was not credited. The application must
validate fictional transaction references, enforce idempotency, reject missing
or unsafe inputs, preserve audit evidence, expose health, readiness, OpenAPI,
case creation, and case inquiry endpoints, and must never perform a real
payment, refund, reversal, network instruction, provider call, deployment, or
certification claim. Human approval remains required for consequential
engineering and all runtime LLM calls must stay at zero.
"""


def _free_port() -> int:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])
    except PermissionError:
        return 0


def _request(
    base_url: str,
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    *,
    expect_json: bool = True,
) -> Any:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        base_url + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        body = response.read()
        if not expect_json:
            return body, response.headers
        return json.loads(body.decode("utf-8"))


def _wait_for_server(base_url: str, process: subprocess.Popen[str]) -> None:
    deadline = time.monotonic() + 20
    last_error = ""
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise AssertionError(f"portal process exited early: {process.stderr.read()}")
        try:
            health = _request(base_url, "GET", "/health")
            if health["status"] == "ok":
                return
        except (OSError, urllib.error.URLError) as exc:
            last_error = str(exc)
        time.sleep(0.2)
    raise AssertionError(f"portal process did not become healthy: {last_error}")


def _wait_for_terminal(base_url: str, run_id: str) -> dict[str, Any]:
    deadline = time.monotonic() + 60
    latest: dict[str, Any] = {}
    while time.monotonic() < deadline:
        latest = _request(base_url, "GET", f"/operator-portal/api/runs/{run_id}")
        if latest["state"] in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            return latest
        time.sleep(0.25)
    raise AssertionError(f"run did not reach terminal state: {latest}")


def _assert_zip_download(content: bytes, expected_member_suffix: str) -> list[str]:
    archive_path = Path("/tmp") / f"portal_e2e_{time.monotonic_ns()}.zip"
    archive_path.write_bytes(content)
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
    archive_path.unlink()
    assert names
    assert len(names) == len(set(names))
    assert all(not name.startswith("/") for name in names)
    assert all(".." not in Path(name).parts for name in names)
    assert any(name.endswith(expected_member_suffix) for name in names)
    return names


def test_operator_portal_live_http_e2e_creates_publishes_and_downloads(tmp_path: Path) -> None:
    port = _free_port()
    if port == 0:
        _run_process_backed_asgi_e2e(tmp_path)
        return
    base_url = f"http://127.0.0.1:{port}"
    browser_root = tmp_path / "browser_runs"
    portfolio_root = PROJECT_ROOT / "workspace/factory_generated" / APP_ID / "live_http_e2e_portfolio" / tmp_path.name
    runtime_root = tmp_path / "runtime"
    launcher = tmp_path / "portal_server.py"
    launcher.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "import sys",
                "import uvicorn",
                f"sys.path.insert(0, {str(PROJECT_ROOT)!r})",
                "from factory.operator_portal.browser_intake_orchestration import BrowserIntakeOrchestrator",
                "from factory.operator_portal.web_ui.app import create_web_ui_app",
                "browser_orchestrator = BrowserIntakeOrchestrator(",
                f"    project_root=Path({str(PROJECT_ROOT)!r}),",
                f"    state_root=Path({str(browser_root)!r}),",
                f"    portfolio_state_root=Path({str(portfolio_root)!r}),",
                ")",
                "app = create_web_ui_app(",
                f"    project_root=Path({str(PROJECT_ROOT)!r}),",
                "    browser_orchestrator=browser_orchestrator,",
                f"    portfolio_state_root=Path({str(portfolio_root)!r}),",
                f"    runtime_state_root=Path({str(runtime_root)!r}),",
                ")",
                "uvicorn.run(app, host='127.0.0.1', port=" + str(port) + ", log_level='warning')",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    process = subprocess.Popen(
        [sys.executable, str(launcher)],
        cwd=Path("/tmp"),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        _wait_for_server(base_url, process)
        html = _request(base_url, "GET", "/operator-ui/", expect_json=False)[0].decode("utf-8")
        assert f'value="{APP_ID}"' in html
        assert "No live provider calls" in html

        validation = _request(
            base_url,
            "POST",
            "/operator-portal/api/requirements/validate",
            {"requirements": REQUIREMENTS_TEXT, "app_id": APP_ID},
        )
        assert validation["status"] == "validated"
        assert validation["validation"]["valid"] is True

        created = _request(
            base_url,
            "POST",
            "/operator-portal/api/runs",
            {"requirements": REQUIREMENTS_TEXT, "app_id": APP_ID},
        )
        assert created["status"] == "run_created"
        assert created["app_id"] == APP_ID
        assert created["real_payment_calls"] == "disabled"
        assert created["llm_calls"] == 0
        run_id = created["run_id"]

        planned = _request(base_url, "POST", f"/operator-portal/api/runs/{run_id}/plan")
        assert planned["run"]["state"] == "AWAITING_APPROVAL"
        assert planned["run"]["plan"]["app_id"] == APP_ID
        assert planned["run"]["plan"]["default_runtime_llm_calls"] == 0

        rejected = None
        try:
            _request(
                base_url,
                "POST",
                f"/operator-portal/api/runs/{run_id}/approvals",
                {"actor": "operator", "approval_token": "wrong"},
            )
        except urllib.error.HTTPError as exc:
            rejected = exc
        assert rejected is not None
        assert rejected.code == 403

        approved = _request(
            base_url,
            "POST",
            f"/operator-portal/api/runs/{run_id}/approvals",
            {"actor": "operator", "approval_token": APPROVAL_TOKEN},
        )
        assert approved["run"]["state"] == "APPROVED"
        assert approved["run"]["approval"]["app_id"] == APP_ID

        first_execute = _request(base_url, "POST", f"/operator-portal/api/runs/{run_id}/execute")
        second_execute = _request(base_url, "POST", f"/operator-portal/api/runs/{run_id}/execute")
        assert first_execute["status"] in {"queued", "already_queued", "already_succeeded"}
        assert second_execute["status"] in {"already_queued", "already_succeeded"}

        terminal = _wait_for_terminal(base_url, run_id)
        assert terminal["state"] == "SUCCEEDED"
        assert terminal["final_decision"] == "GO"
        assert terminal["engineering_result"]["llm_calls"] == 0
        assert terminal["engineering_result"]["real_payment_calls"] == "disabled"
        assert terminal["engineering_result"]["portfolio_registration"]["app_id"] == APP_ID

        catalogue = _request(base_url, "GET", "/operator-portal/api/portfolio/catalogue")
        matching = [item for item in catalogue["versions"] if item["app_id"] == APP_ID and item["generated_run_id"] == run_id]
        assert len(matching) == 1

        validation_report = _request(base_url, "GET", f"/operator-portal/api/runs/{run_id}/validation")
        assert validation_report["mandatory_gates_passed"] is True
        assert validation_report["decision"] == "GO"

        application_zip, app_headers = _request(
            base_url,
            "GET",
            f"/operator-portal/api/runs/{run_id}/downloads/application",
            expect_json=False,
        )
        evidence_zip, evidence_headers = _request(
            base_url,
            "GET",
            f"/operator-portal/api/runs/{run_id}/downloads/evidence",
            expect_json=False,
        )
        assert "application/zip" in app_headers.get("content-type", "")
        assert "application/zip" in evidence_headers.get("content-type", "")
        app_names = _assert_zip_download(application_zip, f"app/{APP_ID}/interfaces/api/main.py")
        evidence_names = _assert_zip_download(evidence_zip, "evidence_manifest.json")
        assert "generated_application/generation_manifest.json" in app_names
        assert "generated_application/docs/DEBUG_PLAN.md" in app_names
        assert "generated_application/evidence/debug_plan.json" in app_names
        assert any(name.endswith("approval_ledger.json") for name in evidence_names)
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)


def _run_process_backed_asgi_e2e(tmp_path: Path) -> None:
    portfolio_root = PROJECT_ROOT / "workspace/factory_generated" / APP_ID / "live_http_e2e_portfolio" / tmp_path.name
    launcher = tmp_path / "portal_asgi_e2e.py"
    output = tmp_path / "asgi_e2e_result.json"
    launcher.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "import json",
                "import sys",
                "import time",
                f"sys.path.insert(0, {str(PROJECT_ROOT)!r})",
                "from factory.operator_portal.browser_intake_orchestration import BrowserIntakeOrchestrator",
                "from factory.operator_portal.portfolio_api import PortfolioAPI",
                f"APP_ID = {APP_ID!r}",
                f"APPROVAL_TOKEN = {APPROVAL_TOKEN!r}",
                f"REQUIREMENTS_TEXT = {REQUIREMENTS_TEXT!r}",
                f"PROJECT_ROOT = Path({str(PROJECT_ROOT)!r})",
                f"portfolio_root = Path({str(portfolio_root)!r})",
                "html = (PROJECT_ROOT / 'factory/operator_portal/web_ui/static/index.html').read_text(encoding='utf-8')",
                "assert f'value=\"{APP_ID}\"' in html",
                "assert 'No live provider calls' in html",
                "browser_orchestrator = BrowserIntakeOrchestrator(",
                "    project_root=PROJECT_ROOT,",
                f"    state_root=Path({str(tmp_path / 'browser_runs')!r}),",
                "    portfolio_state_root=portfolio_root,",
                ")",
                "validation = browser_orchestrator.validate_requirements(REQUIREMENTS_TEXT)",
                "assert validation['status'] == 'validated' and validation['validation']['valid'] is True",
                "created = browser_orchestrator.create_run(REQUIREMENTS_TEXT, app_id=APP_ID)",
                "run_id = created['run_id']",
                "assert created['app_id'] == APP_ID and created['real_payment_calls'] == 'disabled' and created['llm_calls'] == 0",
                "planned = browser_orchestrator.plan(run_id)",
                "assert planned['run']['state'] == 'AWAITING_APPROVAL'",
                "try:",
                "    browser_orchestrator.approve(run_id, actor='operator', approval_token='wrong')",
                "except Exception:",
                "    rejected = True",
                "else:",
                "    rejected = False",
                "assert rejected is True",
                "approved = browser_orchestrator.approve(run_id, actor='operator', approval_token=APPROVAL_TOKEN)",
                "assert approved['run']['state'] == 'APPROVED' and approved['run']['approval']['app_id'] == APP_ID",
                "first = browser_orchestrator.execute(run_id)",
                "second = browser_orchestrator.execute(run_id)",
                "assert first['status'] in {'queued', 'already_queued', 'already_succeeded'}",
                "assert second['status'] in {'already_queued', 'already_succeeded'}",
                "terminal = {}",
                "deadline = time.monotonic() + 60",
                "while time.monotonic() < deadline:",
                "    terminal = browser_orchestrator.get_run(run_id)",
                "    if terminal['state'] in {'SUCCEEDED', 'FAILED', 'CANCELLED'}:",
                "        break",
                "    time.sleep(0.25)",
                "assert terminal['state'] == 'SUCCEEDED', terminal",
                "assert terminal['final_decision'] == 'GO'",
                "assert terminal['engineering_result']['llm_calls'] == 0",
                "assert terminal['engineering_result']['real_payment_calls'] == 'disabled'",
                "catalogue = PortfolioAPI(project_root=PROJECT_ROOT, state_root=portfolio_root).catalogue_payload()",
                "assert [item for item in catalogue['versions'] if item['app_id'] == APP_ID and item['generated_run_id'] == run_id]",
                "validation_report = browser_orchestrator.validation(run_id)",
                "assert validation_report['mandatory_gates_passed'] is True and validation_report['decision'] == 'GO'",
                "app_zip = browser_orchestrator.application_archive(run_id)",
                "evidence_zip = browser_orchestrator.evidence_archive(run_id)",
                f"Path({str(output)!r}).write_text(json.dumps({{'run_id': run_id, 'state': terminal['state'], 'app_zip': app_zip.stat().st_size, 'evidence_zip': evidence_zip.stat().st_size}}), encoding='utf-8')",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    stdout_path = tmp_path / "portal_asgi_e2e.stdout.log"
    stderr_path = tmp_path / "portal_asgi_e2e.stderr.log"
    with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open("w", encoding="utf-8") as stderr:
        completed = subprocess.run(
            [sys.executable, str(launcher)],
            cwd=Path("/tmp"),
            text=True,
            stdout=stdout,
            stderr=stderr,
            timeout=90,
            check=False,
        )
    assert completed.returncode == 0, stderr_path.read_text(encoding="utf-8") or stdout_path.read_text(encoding="utf-8")
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["state"] == "SUCCEEDED"
    assert result["app_zip"] > 0
    assert result["evidence_zip"] > 0
