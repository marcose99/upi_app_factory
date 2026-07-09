from __future__ import annotations

from pathlib import Path
from typing import Any


APP_ID = "upi_dispute_resolution"
PHASE = "phase38_portal_ux_polish_and_operator_guides"
PROJECT_ROOT = Path(__file__).resolve().parents[2]

OPERATOR_GUIDE_SAFETY_BOUNDARIES: dict[str, Any] = {
    "local_only": True,
    "certification_boundary": "certification_ready_not_certified",
    "official_certification_claimed": False,
    "official_certification_granted": False,
    "production_readiness_claimed": False,
    "local_readiness_scope": "local_operator_guides_and_portal_workflows_only",
    "live_provider_calls_allowed": False,
    "real_secrets_allowed": False,
    "deployment_allowed": False,
    "merge_allowed": False,
    "tag_allowed": False,
    "push_allowed": False,
    "external_ecosystem_integrations": "mocked_or_simulated_only",
}

STATUS_TAXONOMY: dict[str, str] = {
    "ok": "The local API process is responding.",
    "available": "A local artifact or report exists and can be read.",
    "missing": "A local artifact is absent; run the documented local command that creates it.",
    "configured": "A local command or workflow is known, but this phase did not execute it.",
    "unavailable": "The local command or workflow is not configured in this checkout.",
    "dry_run": "The validation runner listed approved commands without executing them.",
    "passed": "The local validation command completed with return code 0.",
    "failed": "The local validation command completed with a non-zero return code.",
    "skipped": "The workflow intentionally did not run that action.",
    "export_ready": "A governed local export bundle was created by the existing download center.",
    "error": "The portal could not complete the request; inspect the returned next steps.",
}

GUIDES: tuple[dict[str, str], ...] = (
    {
        "id": "local_operator_guide",
        "title": "Local Operator Guide",
        "path": "docs/phase38/local_operator_guide.md",
        "purpose": "Start, validate, and stop the local factory without live integrations.",
    },
    {
        "id": "troubleshooting_guide",
        "title": "Troubleshooting Guide",
        "path": "docs/phase38/troubleshooting_guide.md",
        "purpose": "Map common portal statuses and failures to local recovery steps.",
    },
    {
        "id": "portal_workflow_guide",
        "title": "Portal Workflow Guide",
        "path": "docs/phase38/portal_workflow_guide.md",
        "purpose": "Use Health, Evidence, Download, Validation, and Guides panels safely.",
    },
    {
        "id": "status_taxonomy",
        "title": "Status Taxonomy",
        "path": "docs/phase38/status_taxonomy.md",
        "purpose": "Explain operator-facing status values and governance boundaries.",
    },
)


def _relative_or_string(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def build_operator_guide_index(project_root: Path | None = None) -> dict[str, Any]:
    root = project_root or PROJECT_ROOT
    guide_entries: list[dict[str, Any]] = []
    for guide in GUIDES:
        path = root / guide["path"]
        guide_entries.append(
            {
                **guide,
                "exists": path.is_file(),
                "resolved_path": _relative_or_string(path, root),
            },
        )

    return {
        "app_id": APP_ID,
        "phase": PHASE,
        "status": "available" if all(entry["exists"] for entry in guide_entries) else "partial",
        "guides": guide_entries,
        "status_taxonomy": STATUS_TAXONOMY,
        "quick_start_commands": [
            {
                "label": "Run Phase 38 validator",
                "command": (
                    ".venv/bin/python "
                    "scripts/validate_phase38_portal_ux_polish_and_operator_guides.py"
                ),
                "expected_output": "Phase 38 portal UX polish and operator guides validated.",
            },
            {
                "label": "Run Phase 38 tests",
                "command": (
                    ".venv/bin/python -m pytest "
                    "tests/test_phase38_portal_ux_polish_and_operator_guides.py"
                ),
                "expected_output": "All Phase 38 tests pass.",
            },
            {
                "label": "Start local portal",
                "command": ".venv/bin/python scripts/run_phase36_operator_portal_local_web_ui.py",
                "expected_output": "A local operator portal URL is printed; no live provider is called.",
            },
        ],
        "operator_boundaries": OPERATOR_GUIDE_SAFETY_BOUNDARIES,
    }
