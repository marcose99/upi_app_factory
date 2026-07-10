from __future__ import annotations

import json
from pathlib import Path

from fastapi.routing import APIRoute

from factory.operator_portal.autonomous_campaign import (
    AutonomousCampaignService,
)
from factory.operator_portal.autonomous_campaign_api import build_router


def write_config(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "campaign_id": "test-campaign",
            }
        ),
        encoding="utf-8",
    )


def test_portal_service_builds_shell_false_run_command(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    config = tmp_path / "campaign.json"
    write_config(config)
    service = AutonomousCampaignService(
        project_root=root,
        campaign_config=config,
        state_root=tmp_path / "state",
    )
    report = service.execute(
        "run",
        dry_run=True,
        approved=True,
    )
    assert report["status"] == "DRY_RUN"
    assert report["shell"] is False
    assert "--resume" in report["command"]


def test_portal_service_reports_not_started(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    config = tmp_path / "campaign.json"
    write_config(config)
    service = AutonomousCampaignService(
        project_root=root,
        campaign_config=config,
        state_root=tmp_path / "state",
    )
    assert service.status()["status"] == "NOT_STARTED"


def test_router_exposes_status_events_and_actions(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    config = tmp_path / "campaign.json"
    write_config(config)
    router = build_router(
        project_root=root,
        campaign_config=config,
    )
    paths = {
        route.path
        for route in router.routes
        if isinstance(route, APIRoute)
    }
    assert "/api/autonomous-campaign/status" in paths
    assert "/api/autonomous-campaign/events" in paths
    assert "/api/autonomous-campaign/{action}" in paths
