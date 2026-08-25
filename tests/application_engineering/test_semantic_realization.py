from __future__ import annotations

import copy
import json
from typing import Any

import pytest

from factory.application_engineering.semantic_realization import (
    SemanticRealizationError,
    build_semantic_model,
    render_semantic_files,
    semantic_fingerprint,
)


def _ir(signal: str = "review_complete") -> dict[str, Any]:
    return {
        "schema_version": "requirements-ir/v1",
        "actors": [{"id": "ACT-1", "name": "reviewer"}],
        "commands": [{"id": "CMD-1", "name": signal}],
        "events": [{"id": "EVT-1", "name": f"{signal}_recorded"}],
        "workflows": [
            {
                "id": "WF-1",
                "from": "received",
                "to": "reviewed",
                "signal": signal,
                "deadline": "P1D",
                "reentry": "additional_evidence",
                "human_review": True,
            }
        ],
        "security": [{"id": "SEC-1", "description": "local fictional data only"}],
    }


def test_distinct_requirement_semantics_have_distinct_executable_models_and_fingerprints() -> None:
    first = build_semantic_model(_ir("review_complete"))
    second = build_semantic_model(_ir("risk_rejected"))
    assert first["commands"] != second["commands"]
    assert first["events"] != second["events"]
    assert (
        first["state_machine"]["valid_transitions"] != second["state_machine"]["valid_transitions"]
    )
    assert semantic_fingerprint(first) != semantic_fingerprint(second)


def test_semantic_model_is_source_location_independent_and_tamper_checked() -> None:
    ir = _ir()
    ir["commands"][0]["source"] = {"path": "/clone/a.md", "line": 30}
    first = build_semantic_model(ir)
    ir["commands"][0]["source"] = {"path": "/other/b.md", "line": 99}
    assert build_semantic_model(ir)["semantic_fingerprint"] == first["semantic_fingerprint"]
    tampered = copy.deepcopy(first)
    tampered["commands"][0]["name"] = "changed"
    with pytest.raises(SemanticRealizationError, match="fingerprint"):
        render_semantic_files(tampered, "sample_app")


def test_rendered_json_is_authoritative_and_module_is_deterministic() -> None:
    model = build_semantic_model(_ir())
    first = render_semantic_files(model, "sample_app")
    second = render_semantic_files(model, "sample_app")
    assert first == second
    assert (
        json.loads(first["evidence/semantic_model.json"])["semantic_fingerprint"]
        == model["semantic_fingerprint"]
    )
    assert "review_complete" in first["app/sample_app/semantic_policy.py"]
