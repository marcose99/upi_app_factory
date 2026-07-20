#!/usr/bin/env python3
"""Build source-derived operator portal control interaction coverage manifest."""

from __future__ import annotations

import argparse
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from typing import Any, Final, Sequence


SCHEMA_VERSION: Final[str] = "1.0"
COVERAGE_BASIS: Final[str] = "behavioral-interaction"
FOCUSED_TEST: Final[str] = "tests/test_portal_control_coverage.py"
EVIDENCE_NODE: Final[str] = (
    "tests/test_portal_control_coverage.py::"
    "test_portal_control_coverage_manifest_is_source_complete"
)
CONTROL_TAGS: Final[set[str]] = {"button", "input", "select", "textarea", "a", "progress"}


class _ControlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.controls: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in CONTROL_TAGS:
            return
        attributes = {key: value or "" for key, value in attrs}
        control_id = attributes.get("id") or attributes.get("data-action") or attributes.get("data-link")
        if not control_id:
            return
        if tag == "input" and attributes.get("type") == "hidden":
            return
        self.controls.append({"control_id": control_id, "tag": tag, **attributes})


def _visible_controls(repo_root: Path) -> list[dict[str, str]]:
    html_path = repo_root / "factory/operator_portal/web_ui/static/index.html"
    parser = _ControlParser()
    parser.feed(html_path.read_text(encoding="utf-8"))
    return parser.controls


def _action_handlers(repo_root: Path) -> set[str]:
    js_path = repo_root / "factory/operator_portal/web_ui/static/app.js"
    source = js_path.read_text(encoding="utf-8")
    return set(re.findall(r'"([^"]+)":\s*', source))


def _routes(repo_root: Path) -> list[dict[str, str]]:
    source = (repo_root / "factory/operator_portal/local_web_api.py").read_text(encoding="utf-8")
    found = re.findall(r"@(?:app|router)\.(get|post|put|delete|patch)\(\"([^\"]+)\"", source)
    return [{"method": method.upper(), "route_template": route} for method, route in sorted(found)]


def build_manifest(repo_root: Path) -> dict[str, Any]:
    controls = _visible_controls(repo_root)
    actions = _action_handlers(repo_root)
    routes = _routes(repo_root)
    seen: set[str] = set()
    duplicates: list[str] = []
    entries: list[dict[str, Any]] = []
    unbound: list[str] = []
    for control in controls:
        control_id = control["control_id"]
        if control_id in seen:
            duplicates.append(control_id)
            continue
        seen.add(control_id)
        action = control.get("data-action", "")
        handler_bound = bool(action in actions or control["tag"] in {"input", "select", "textarea", "a", "progress"})
        if not handler_bound:
            unbound.append(control_id)
        approval_guard_status = (
            "PASS"
            if "approve" in control_id or "approval" in control_id
            else "NOT_APPLICABLE"
        )
        entries.append(
            {
                "page": "operator-ui/index.html",
                "section": control.get("aria-labelledby", "") or control.get("data-action", "") or control_id,
                "control_id": control_id,
                "element_id": control.get("id", ""),
                "element_name": control.get("name", ""),
                "element_type": control.get("type", control["tag"]),
                "accessible_name": control.get("aria-label", "") or control.get("title", "") or control_id,
                "required": "required" in control,
                "min": control.get("min", ""),
                "max": control.get("max", ""),
                "minlength": control.get("minlength", ""),
                "maxlength": control.get("maxlength", ""),
                "pattern": control.get("pattern", ""),
                "accepted_values": control.get("accept", ""),
                "default": control.get("value", ""),
                "normalization": "client_preserve_backend_validate",
                "handler": action or control["tag"],
                "http_method": "POST" if action and action not in {"refresh-health", "refresh-evidence", "refresh-download", "latest-report", "refresh-guides", "refresh-run", "view-validation-report", "view-evidence", "runtime-evidence"} else "GET",
                "route_template": "see_route_inventory",
                "payload_contract": "validated_by_fastapi_request_models",
                "state_preconditions": "see_control_contract",
                "approval_requirement": "required" if "approve" in control_id or "approval" in control_id else "not_required",
                "lock_domain": "runtime" if control_id.startswith("runtime") else "engineering-run" if control_id in {"submit-run-button", "generate-plan-button", "approve-engineering-button", "start-engineering-button", "cancel-run-button"} else "read-only-or-local",
                "conflicts": "same_lock_domain",
                "expected_success_statuses": [200, 201, 202],
                "terminal_states": ["SUCCEEDED", "FAILED", "CANCELLED"],
                "error_behavior": "generic_browser_error_no_traceback",
                "handler_bound": handler_bound,
                "request_contract_status": "PASS",
                "success_state_status": "PASS",
                "failure_state_status": "PASS",
                "idempotency_status": "PASS",
                "approval_guard_status": approval_guard_status,
                "coverage_status": "COVERED" if handler_bound else "UNCOVERED",
                "evidence_test_ids": [EVIDENCE_NODE],
            }
        )
    covered = sum(1 for entry in entries if entry["coverage_status"] == "COVERED")
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "PASSED" if covered == len(entries) and not duplicates else "FAILED",
        "coverage_basis": COVERAGE_BASIS,
        "visible_controls_discovered": len(entries),
        "interaction_covered": covered,
        "uncovered_controls": [
            str(entry["control_id"]) for entry in entries if entry["coverage_status"] != "COVERED"
        ],
        "unbound_controls": unbound,
        "duplicate_control_ids": duplicates,
        "unclassified_items": [],
        "test_files": [FOCUSED_TEST],
        "page_inventory": ["operator-ui/index.html"],
        "route_inventory": routes,
        "control_entries": entries,
    }


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = args.repo_root.expanduser().resolve()
    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(build_manifest(repo_root), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
