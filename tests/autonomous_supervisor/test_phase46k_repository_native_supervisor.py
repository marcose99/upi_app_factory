from __future__ import annotations

import json
from pathlib import Path

from tools.autonomous_supervisor.catalog import RepairCatalog
from tools.autonomous_supervisor.cli import build_parser
from tools.autonomous_supervisor.engine import (
    candidate_paths,
    validate_configuration,
)


def test_cli_exposes_repository_native_commands() -> None:
    parser = build_parser()
    help_text = parser.format_help()
    assert "run" in help_text
    assert "validate" in help_text
    assert "pause" in help_text
    assert "resume" in help_text
    assert "cancel" in help_text


def test_repair_catalog_loads_repository_policy(
    tmp_path: Path,
) -> None:
    path = tmp_path / "catalog.json"
    path.write_text(
        json.dumps(
            {
                "repairs": [
                    {
                        "repair_id": "RUFF_SAFE_FIX",
                        "automatic": True,
                        "eligible_gates": ["Ruff"],
                        "max_attempts": 2,
                        "candidate_scope_required": True,
                        "safe_fix_only": True,
                        "risk": "LOW",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    catalog = RepairCatalog.load(path)
    rule = catalog.automatic_rule_for_gate("Ruff")
    assert rule is not None
    assert rule.repair_id == "RUFF_SAFE_FIX"


def test_candidate_paths_are_read_from_manifest(
    tmp_path: Path,
) -> None:
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps({"candidate_paths": ["a.py", "b.json"]}),
        encoding="utf-8",
    )
    assert candidate_paths(path) == ["a.py", "b.json"]


def test_repository_configuration_validates(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    for relative in (
        "campaign.json",
        "catalog.json",
        "prerequisites.json",
        "noise.json",
        "limits.json",
    ):
        (root / relative).write_text("{}\n", encoding="utf-8")
    (root / "catalog.json").write_text(
        json.dumps({"repairs": []}),
        encoding="utf-8",
    )
    config = root / "autonomous.json"
    config.write_text(
        json.dumps(
            {
                "campaign_id": "test",
                "phases": ["99A"],
                "campaign_manifest": "campaign.json",
                "repair_catalog": "catalog.json",
                "prerequisite_manifest": "prerequisites.json",
                "runtime_noise_policy": "noise.json",
                "supervisor_limits": "limits.json",
            }
        ),
        encoding="utf-8",
    )
    report = validate_configuration(root, config)
    assert report["status"] == "PASSED"
    assert report["phase_count"] == 1
