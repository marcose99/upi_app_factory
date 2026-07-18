from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from factory.operator_portal.local_web_api import create_app
from upi_factory.capstone.phase69 import (
    CAMPAIGN_ID,
    read_safe_source,
    run_phase69_demonstration,
    validate_phase69_demonstration,
)


ROOT = Path(__file__).resolve().parents[2]


def test_phase69_demonstration_closes_from_control_plane_state(tmp_path: Path) -> None:
    result = run_phase69_demonstration(project_root=ROOT, state_root=tmp_path / "state", write_evidence=False)
    portal = result["portal"]

    assert result["status"] == "PASS"
    assert portal["campaign_id"] == CAMPAIGN_ID
    assert portal["control_plane"]["source_of_truth"] is True
    assert portal["control_plane"]["event_count"] > 0
    assert portal["kpis"]["completion_percent"] == 100
    assert all(item["status"] == "completed" for item in portal["dependency_activity_state"])
    assert portal["recipient_download"]["status"] == "PASS"
    assert portal["generated_application_portfolio"]["profile_count"] == 6
    assert portal["evidence_integrity"]["record_count"] >= 3
    assert portal["real_payment_calls"] == "disabled"
    assert portal["official_certification_claimed"] is False


def test_phase69_portal_api_html_openapi_and_download_are_browserless() -> None:
    with tempfile.TemporaryDirectory(prefix="upi_phase69_portal_api_", dir="/tmp") as temporary:
        isolated = Path(temporary)
        app = create_app(
            project_root=ROOT,
            runtime_state_root=isolated / "runtime",
            portfolio_state_root=isolated / "portfolio",
            phase69_state_root=isolated / "phase69",
        )
        client = TestClient(app)

        demo = client.post("/operator-portal/api/capstone/phase69/demonstration")
        assert demo.status_code == 200, demo.text
        payload = demo.json()
        assert payload["status"] == "PASS"

        status = client.get("/operator-portal/api/capstone/phase69/status")
        assert status.status_code == 200
        assert status.json()["kpis"]["completion_percent"] == 100

        html = client.get("/operator-portal/api/capstone/phase69/view")
        assert html.status_code == 200
        assert "Governed Portfolio Operations" not in html.text
        assert "UPI App Factory Control Plane Campaign" in html.text

        openapi = client.get("/openapi.json")
        assert openapi.status_code == 200
        assert "/operator-portal/api/capstone/phase69/status" in openapi.json()["paths"]

        download = client.get("/operator-portal/api/capstone/phase69/downloads/recipient")
        assert download.status_code == 200
        assert download.content.startswith(b"PK")


def test_phase69_safe_source_browsing_rejects_traversal() -> None:
    source = read_safe_source(ROOT, "phase69.py")
    assert source["status"] == "available"
    assert source["path"] == "phase69.py"

    try:
        read_safe_source(ROOT, "../../config/control_plane/standing_policy.json")
    except Exception as exc:
        assert "outside the safe" in str(exc)
    else:
        raise AssertionError("unsafe source path was accepted")


def test_phase69_validator_function_and_cli_pass() -> None:
    result = validate_phase69_demonstration(project_root=ROOT)
    assert result["status"] == "PASS"
    assert result["errors"] == []

    completed = subprocess.run(
        [sys.executable, "scripts/validate_phase69_control_plane_portal_demonstration.py"],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["status"] == "PASS"
