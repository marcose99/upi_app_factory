from fastapi.testclient import TestClient

from app.main import app


def test_feedback_submission_and_read() -> None:
    client = TestClient(app)
    response = client.post(
        "/feedback",
        json={
            "title": "Improve state machine clarity",
            "description": "Add explicit rejected and escalated transition examples.",
            "reviewer_role": "TECHNICAL_REVIEWER",
            "severity": "MEDIUM",
            "quality_dimensions": ["DOCUMENTATION_CLARITY", "DEBUGGABILITY"],
        },
    )
    assert response.status_code == 200
    feedback = response.json()
    assert feedback["feedback_id"].startswith("FB-")
    assert feedback["status"] == "SUBMITTED"

    read_response = client.get(f"/feedback/{feedback['feedback_id']}")
    assert read_response.status_code == 200
    assert read_response.json()["title"] == "Improve state machine clarity"


def test_open_blocker_report() -> None:
    client = TestClient(app)
    response = client.get("/feedback/reports/open-blockers")
    assert response.status_code == 200
    assert "open_blocker_count" in response.json()
