from __future__ import annotations

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_complete_technical_guide_covers_required_subjects() -> None:
    html = (PROJECT_ROOT / "docs/factory/UPI_APP_FACTORY_COMPLETE_GUIDE.html").read_text(encoding="utf-8")
    required_subjects = [
        "Executive technical summary",
        "Truth and trust boundaries",
        "System context",
        "Runtime topology",
        "Repository architecture",
        "Agent and task ownership",
        "Requirements compilation",
        "LLM and prompt strategy",
        "Knowledge retrieval",
        "Tool routing and safeguards",
        "Planning, memory, and adaptation",
        "Operator portal lifecycle",
        "Generated application architecture",
        "Persistence and consistency",
        "Governance and evidence",
        "Security engineering",
        "Observability and debugging",
        "Testing and quality gates",
        "Deployment and portability",
        "Failure modes and recovery",
        "Limitations and non-claims",
        "Source traceability",
    ]
    for subject in required_subjects:
        assert subject in html
    assert "<details>" in html and "<summary>" in html
    for blocked_placeholder in ["TO" + "DO", "T" + "BD"]:
        assert blocked_placeholder not in html


def test_complete_technical_manifest_records_diagram_and_animation_evidence() -> None:
    manifest = json.loads((PROJECT_ROOT / "docs/factory/UPI_APP_FACTORY_COMPLETE_GUIDE.manifest.json").read_text(encoding="utf-8"))
    assert manifest["reduced_motion_policy"]["css_media_query"] == "@media (prefers-reduced-motion: reduce)"
    assert manifest["reduced_motion_policy"]["animated_classes"]
    assert len({item["id"] for item in manifest["animations"]}) >= 4
    assert len({item["id"] for item in manifest["diagrams"]}) >= 8
    for animation in manifest["animations"]:
        assert animation["purpose"]
        assert animation["mechanism"]
        assert "prefers-reduced-motion" in animation["reduced_motion"]
        assert animation["source_claim_ids"]
    for diagram in manifest["diagrams"]:
        assert diagram["purpose"]
        assert diagram["source_claim_ids"]
