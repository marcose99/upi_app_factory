from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.application_engineering.deep_composer import DeepApplicationComposer, DeepComposerError
from factory.quality_assurance.kernel import DIMENSION_WEIGHTS, HARD_GATES


def _raw_measures() -> dict[str, object]:
    return {
        "dimensions": {name: {"met": 1, "total": 1} for name in DIMENSION_WEIGHTS},
        "hard_gates": {
            name: {"met": 1, "total": 1, "evidence_ids": ["qualification-run"]}
            for name in HARD_GATES
        },
    }


def test_composer_rejects_requirements_supplied_quality_measurements(tmp_path: Path) -> None:
    output_root = tmp_path / "generated"
    requirements = {
        "quality_assurance": {
            "claims": [],
            "evidence": [
                {
                    "evidence_id": "qualification-run",
                    "source": "test",
                    "version": "1",
                    "sha256": "0" * 64,
                    "location": "tests/application_engineering",
                    "method": "executable test",
                    "result": "PASS",
                }
            ],
            "raw_measures": _raw_measures(),
        }
    }

    with pytest.raises(DeepComposerError, match="cannot supply raw_measures"):
        DeepApplicationComposer(tmp_path).compose(
            requirements_ir=requirements,
            output_root=output_root,
            app_id="quality_probe",
        )

    assurance_root = output_root / "quality_probe" / "evidence" / "quality_assurance"
    assert not assurance_root.exists()


def test_composer_supports_isolated_campaign_root_outside_worktree(tmp_path: Path) -> None:
    project_root = tmp_path / "source"
    output_root = tmp_path / "campaign" / "generation"

    DeepApplicationComposer(project_root).compose(
        requirements_ir={},
        output_root=output_root,
        app_id="campaign_probe",
    )

    assert (output_root / "campaign_probe").is_dir()


def test_composer_rejects_project_ancestor_as_output_root(tmp_path: Path) -> None:
    project_root = tmp_path / "source"
    with pytest.raises(DeepComposerError, match="project root or its ancestor"):
        DeepApplicationComposer(project_root).compose(
            requirements_ir={},
            output_root=tmp_path,
            app_id="unsafe_probe",
        )

def test_semantic_overlay_preserves_legacy_api_and_mounts_only_new_routes(tmp_path: Path) -> None:
    output_root = tmp_path / "semantic-overlay"
    requirements = {
        "workflows": [
            {"id": "WF-1", "from": "received", "to": "reviewed", "signal": "review"}
        ],
        "events": [{"id": "EV-1", "name": "reviewed"}],
        "apis": [
            {"id": "API-CUSTOM", "method": "GET", "path": "/v1/custom-semantic"},
            {"id": "API-LEGACY", "method": "GET", "path": "/v1/disputes/{dispute_id}/timeline"},
        ],
    }
    DeepApplicationComposer(tmp_path / "source").compose(
        requirements_ir=requirements,
        output_root=output_root,
        app_id="semantic_overlay_probe",
    )
    root = output_root / "semantic_overlay_probe"
    main_text = (root / "app/semantic_overlay_probe/interfaces/api/main.py").read_text(encoding="utf-8")
    routes_text = (root / "app/semantic_overlay_probe/interfaces/api/semantic_routes.py").read_text(encoding="utf-8")
    assert "def get_timeline" in main_text
    assert "return service._cases[dispute_id].timeline" in main_text
    assert "app.include_router(semantic_router)" in main_text
    assert '@router.get("/v1/custom-semantic")' in routes_text
    assert "/v1/disputes/{dispute_id}/timeline" not in routes_text


def test_semantic_overlay_accepts_conceptual_api_requirement_without_inventing_route(tmp_path: Path) -> None:
    output_root = tmp_path / "conceptual-api-overlay"
    requirements = {
        "workflows": [{"id": "WF-1", "from": "received", "to": "reviewed", "signal": "review"}],
        "events": [{"id": "EV-1", "name": "reviewed"}],
        "apis": [{"id": "API-CONCEPT", "name": "Local API capability", "description": "Commands and queries are exposed through local services; no HTTP route is specified."}],
    }
    DeepApplicationComposer(tmp_path / "source").compose(
        requirements_ir=requirements, output_root=output_root, app_id="conceptual_api_probe"
    )
    root = output_root / "conceptual_api_probe"
    routes_text = (root / "app/conceptual_api_probe/interfaces/api/semantic_routes.py").read_text(encoding="utf-8")
    evidence = json.loads((root / "evidence/runtime_architecture.json").read_text(encoding="utf-8"))
    assert "@router." not in routes_text
    assert evidence["api_route_contract"]["conceptual_api_requirement_ids"] == ["API-CONCEPT"]

def test_base_api_supports_architecture_composition_root_fallback(tmp_path: Path) -> None:
    composer = DeepApplicationComposer(tmp_path)
    files = composer._render_files("sample_app", "0" * 64, {})
    api = files["app/sample_app/interfaces/api/main.py"]
    assert "application.composition_root" in api
    assert "service = build_dispute_service()" in api
