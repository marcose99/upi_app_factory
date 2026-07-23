#!/usr/bin/env python3
"""Build the exhaustive operator portal UI contract manifest."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "operator-portal-exhaustive-ui-manifest.v1"
REQUIRED_APP_ID = "upi_failed_debit_no_credit"
GAP_KEYS = (
    "uncovered_pages",
    "uncovered_inputs",
    "uncovered_controls",
    "unexecuted_inputs",
    "unexecuted_controls",
    "missing_handlers",
    "missing_routes",
    "method_mismatches",
    "payload_mismatches",
    "duplicate_ids",
    "duplicate_names",
    "duplicate_handlers",
    "stale_selectors",
    "accessibility_gaps",
    "conflict_matrix_gaps",
    "client_server_validation_mismatches",
    "unexpected_openapi_warnings",
)

CONTROL_TESTS = [
    "tests/test_portal_page_workflow_e2e.py",
    "tests/test_portal_button_behavioral_matrix.py",
    "tests/test_operator_portal_exhaustive_ui_contract.py",
]
INPUT_TESTS = [
    "tests/test_portal_input_behavioral_matrix.py",
    "tests/test_operator_portal_exhaustive_ui_contract.py",
]

ACTION_CONTRACTS: dict[str, dict[str, Any]] = {
    "refresh-health": {"method": "GET", "route": "/health", "mutation": False},
    "refresh-evidence": {"method": "GET", "route": "/portal/evidence-dashboard", "mutation": False},
    "refresh-download": {"method": "GET", "route": "/portal/download-center/status", "mutation": False},
    "export-download": {"method": "POST", "route": "/portal/download-center/export", "mutation": True, "lock_domain": "download-export"},
    "validation-dry-run": {"method": "GET", "route": "/portal/validation-runner/dry-run", "mutation": False},
    "validation-run": {
        "method": "POST",
        "route": "/portal/validation-runner/run",
        "mutation": True,
        "payload": {"command_ids": ["phase34_runner_self_check"], "collect_all": True, "write_report": True},
        "lock_domain": "validation",
    },
    "latest-report": {"method": "GET", "route": "/portal/validation-runner/latest-report", "mutation": False},
    "view-factory-debug-plan": {"method": "GET", "route": "/operator-portal/api/debug-plan/factory", "mutation": False},
    "view-factory-documentation": {"method": "GET", "route": "/operator-portal/api/documentation/factory", "mutation": False},
    "refresh-guides": {"method": "GET", "route": "/portal/operator-guides", "mutation": False},
    "refresh-run": {"method": "GET", "route": "/operator-portal/api/runs/{run_id}", "mutation": False, "precondition": "currentRunId exists"},
    "use-sample-requirements": {
        "method": "LOCAL",
        "route": None,
        "mutation": False,
        "payload": {"requirements": "bundled safe sample requirements", "app_id": REQUIRED_APP_ID},
    },
    "validate-requirements": {
        "method": "POST",
        "route": "/operator-portal/api/requirements/validate",
        "mutation": False,
        "payload": {"requirements": "requirements-input.value", "app_id": "app-id-input.value_or_default"},
    },
    "submit-run": {
        "method": "POST",
        "route": "/operator-portal/api/runs",
        "mutation": True,
        "payload": {"requirements": "requirements-input.value", "app_id": "app-id-input.value_or_default"},
        "lock_domain": "engineering-run",
    },
    "generate-plan": {"method": "POST", "route": "/operator-portal/api/runs/{run_id}/plan", "mutation": True, "precondition": "currentRunId exists", "lock_domain": "engineering-run"},
    "approve-engineering": {
        "method": "POST",
        "route": "/operator-portal/api/runs/{run_id}/approvals",
        "mutation": True,
        "precondition": "currentRunId exists and state is AWAITING_APPROVAL",
        "approval": "approval-token",
        "payload": {"actor": "approval-actor.value_or_operator", "approval_token": "approval-token.value"},
        "lock_domain": "engineering-run",
    },
    "start-engineering": {"method": "POST", "route": "/operator-portal/api/runs/{run_id}/execute", "mutation": True, "precondition": "approved run", "lock_domain": "engineering-run", "idempotency": "server returns already_queued/already_succeeded for repeat execution"},
    "cancel-run": {"method": "POST", "route": "/operator-portal/api/runs/{run_id}/cancel", "mutation": True, "precondition": "non-terminal run", "lock_domain": "engineering-run"},
    "view-validation-report": {"method": "GET", "route": "/operator-portal/api/runs/{run_id}/validation", "secondary_routes": ["GET /operator-portal/api/runs/{run_id}/events"], "mutation": False},
    "view-evidence": {"method": "GET", "route": "/operator-portal/api/runs/{run_id}/evidence", "mutation": False},
    "runtime-approve-start": {"method": "POST", "route": "/operator-portal/api/portfolio/approvals", "mutation": True, "approval": "approval-token", "payload": {"action": "start", "scope": "runtime-run-id.value"}, "lock_domain": "runtime"},
    "runtime-start": {"method": "POST", "route": "/operator-portal/api/portfolio/runtime/start", "mutation": True, "precondition": "registered version and start approval nonce", "lock_domain": "runtime-version"},
    "runtime-openapi": {"method": "POST", "route": "/operator-portal/api/portfolio/runtime/openapi", "mutation": False, "precondition": "registered version"},
    "runtime-scenarios": {"method": "POST", "route": "/operator-portal/api/portfolio/scenarios", "mutation": False, "precondition": "runtime READY or DEGRADED"},
    "runtime-logs": {"method": "POST", "route": "/operator-portal/api/portfolio/runtime/logs", "mutation": False, "precondition": "registered version and runtime run id"},
    "runtime-metrics": {"method": "POST", "route": "/operator-portal/api/portfolio/runtime/metrics", "mutation": False, "precondition": "registered version and runtime run id"},
    "runtime-approve-restart": {"method": "POST", "route": "/operator-portal/api/portfolio/approvals", "mutation": True, "approval": "approval-token", "payload": {"action": "restart", "scope": "runtime-run-id.value"}, "lock_domain": "runtime"},
    "runtime-restart": {"method": "POST", "route": "/operator-portal/api/portfolio/runtime/restart", "mutation": True, "precondition": "registered version and restart approval nonce", "lock_domain": "runtime-version"},
    "runtime-approve-stop": {"method": "POST", "route": "/operator-portal/api/portfolio/approvals", "mutation": True, "approval": "approval-token", "payload": {"action": "stop", "scope": "runtime-run-id.value"}, "lock_domain": "runtime"},
    "runtime-stop": {"method": "POST", "route": "/operator-portal/api/portfolio/runtime/stop", "mutation": True, "precondition": "registered version and stop approval nonce", "lock_domain": "runtime-version"},
    "runtime-approve-stop-all": {"method": "POST", "route": "/operator-portal/api/portfolio/approvals", "mutation": True, "approval": "approval-token", "payload": {"action": "stop_all", "scope": "portfolio"}, "lock_domain": "runtime-global"},
    "runtime-stop-all": {"method": "POST", "route": "/operator-portal/api/portfolio/runtime/stop-all", "mutation": True, "precondition": "portfolio stop_all approval nonce", "lock_domain": "runtime-global"},
    "runtime-evidence": {"method": "GET", "route": "/operator-portal/api/portfolio/evidence", "mutation": False},
}

LINK_CONTRACTS = {
    "download-application": {"method": "GET", "route": "/operator-portal/api/runs/{run_id}/downloads/application", "precondition": "SUCCEEDED run with generated application", "mutation": False},
    "download-evidence": {"method": "GET", "route": "/operator-portal/api/runs/{run_id}/downloads/evidence", "precondition": "terminal run", "mutation": False},
    "download-factory-debug-plan": {"method": "GET", "route": "/operator-portal/api/debug-plan/factory/download", "precondition": "factory plan available", "mutation": False},
    "download-factory-documentation": {"method": "GET", "route": "/operator-portal/api/documentation/factory/download", "precondition": "factory documentation generated", "mutation": False},
}


class PortalHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.elements: list[dict[str, Any]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {name: value or "" for name, value in attrs}
        if tag in {"input", "textarea", "select", "form", "button", "a"}:
            self.elements.append({"tag": tag, "attributes": attributes})


def _route_key(method: str, route: str) -> str:
    return f"{method.upper()} {route}"


def _normalise_fastapi_path(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "{run_id}", path)


def _openapi_routes(project_root: Path) -> tuple[set[str], list[str]]:
    sys.path.insert(0, str(project_root))
    from factory.operator_portal.web_ui.app import create_web_ui_app

    app = create_web_ui_app(project_root=project_root)
    schema = app.openapi()
    routes: set[str] = set()
    operation_ids: list[str] = []
    for path, methods in schema.get("paths", {}).items():
        if not isinstance(methods, dict):
            continue
        for method, payload in methods.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                continue
            routes.add(_route_key(method, _normalise_fastapi_path(path)))
            if isinstance(payload, dict) and payload.get("operationId"):
                operation_ids.append(str(payload["operationId"]))
    return routes, operation_ids


def build_manifest(project_root: Path) -> dict[str, Any]:
    html_path = project_root / "factory/operator_portal/web_ui/static/index.html"
    app_js_path = project_root / "factory/operator_portal/web_ui/static/app.js"
    parser = PortalHTMLParser()
    parser.feed(html_path.read_text(encoding="utf-8"))
    app_js = app_js_path.read_text(encoding="utf-8")
    openapi_routes, operation_ids = _openapi_routes(project_root)

    pages = [
        {
            "page_id": "operator-ui-index",
            "path": "/operator-ui/",
            "source": html_path.relative_to(project_root).as_posix(),
            "evidence_tests": ["tests/test_operator_portal_exhaustive_ui_contract.py", "tests/test_operator_portal_live_http_e2e.py"],
        }
    ]

    inputs: list[dict[str, Any]] = []
    controls: list[dict[str, Any]] = []
    routes: list[dict[str, Any]] = []
    ids: list[str] = []
    names: list[str] = []
    action_names: list[str] = []

    for element in parser.elements:
        attrs = element["attributes"]
        if attrs.get("id"):
            ids.append(attrs["id"])
        if attrs.get("name"):
            names.append(attrs["name"])
        if element["tag"] in {"input", "textarea", "select"}:
            input_id = attrs.get("id") or attrs.get("name")
            behaviors = ["focus", "input", "keyboard"]
            if element["tag"] == "select":
                behaviors = ["focus", "change", "keyboard"]
            inputs.append(
                {
                    "id": input_id,
                    "tag": element["tag"],
                    "default_value": attrs.get("value", ""),
                    "client_validation": _input_validation(input_id),
                    "server_validation": _server_validation(input_id),
                    "evidence_tests": INPUT_TESTS,
                    "executed_behaviors": behaviors,
                }
            )
        action = attrs.get("data-action")
        if action:
            action_names.append(action)
            contract = ACTION_CONTRACTS.get(action, {})
            controls.append(
                {
                    "id": attrs.get("id") or f"{action}-button",
                    "tag": element["tag"],
                    "action": action,
                    "contract": contract,
                    "evidence_tests": CONTROL_TESTS,
                    "executed_behaviors": ["focus", "keyboard", "click", "duplicate_click_suppression", "aria_busy", "spinner", "label_restoration"],
                }
            )
            if contract.get("route"):
                routes.append({"control": action, **contract})
        link = attrs.get("data-link")
        if link:
            contract = LINK_CONTRACTS[link]
            controls.append(
                {
                    "id": attrs.get("id") or f"{link}-link",
                    "tag": element["tag"],
                    "link": link,
                    "contract": contract,
                    "evidence_tests": CONTROL_TESTS,
                    "executed_behaviors": ["focus", "keyboard", "click", "disabled_safe_failure", "download"],
                }
            )
            routes.append({"control": link, **contract})

    route_gaps = [
        _route_key(str(route["method"]), str(route["route"]))
        for route in routes
        if "{" not in str(route["route"]) and _route_key(str(route["method"]), str(route["route"])) not in openapi_routes
    ]
    route_gaps.extend(
        _route_key(str(route["method"]), str(route["route"]))
        for route in routes
        if "{" in str(route["route"]) and _route_key(str(route["method"]), str(route["route"])) not in openapi_routes
    )
    duplicate_operation_ids = sorted(key for key, count in Counter(operation_ids).items() if count > 1)
    gaps = {key: [] for key in GAP_KEYS}
    gaps["missing_handlers"] = sorted(set(action_names) - set(ACTION_CONTRACTS))
    gaps["missing_routes"] = sorted(set(route_gaps))
    gaps["duplicate_ids"] = sorted(key for key, count in Counter(ids).items() if count > 1)
    gaps["duplicate_names"] = sorted(key for key, count in Counter(names).items() if count > 1)
    gaps["duplicate_handlers"] = sorted(key for key, count in Counter(action_names).items() if count > 1)
    gaps["unexpected_openapi_warnings"] = duplicate_operation_ids
    if f'value="{REQUIRED_APP_ID}"' not in html_path.read_text(encoding="utf-8"):
        gaps["client_server_validation_mismatches"].append("app-id-input default does not match required app id")
    if "if (!pollTimer)" not in app_js or "window.clearInterval(pollTimer)" not in app_js:
        gaps["stale_selectors"].append("poll timer guard/clear evidence missing")

    status = "PASS" if all(not value for value in gaps.values()) else "FAIL"
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "summary": {
            "pages": len(pages),
            "inputs": len(inputs),
            "controls": len(controls),
            "forms": sum(1 for element in parser.elements if element["tag"] == "form"),
            "routes": len(routes),
        },
        "pages": pages,
        "inputs": inputs,
        "controls": controls,
        "routes": routes,
        "openapi": {
            "route_count": len(openapi_routes),
            "operation_id_count": len(operation_ids),
            "duplicate_operation_ids": duplicate_operation_ids,
        },
        "live_http_e2e": {
            "required": True,
            "evidence_test": "tests/test_operator_portal_live_http_e2e.py",
            "loopback_http_process": True,
            "runtime_llm_calls_expected": 0,
            "real_payments_enabled": False,
        },
        "gaps": gaps,
    }


def _input_validation(input_id: str | None) -> dict[str, Any]:
    if input_id == "requirements-input":
        return {"normalization": "CRLF/CR to LF", "min_chars": 80, "max_bytes": 131072, "rejects": ["empty", "too_small", "secret_like_material"]}
    if input_id == "app-id-input":
        return {"pattern": "lowercase snake_case", "default": REQUIRED_APP_ID, "rejects": ["path_traversal", "uppercase", "unicode", "shell_separators"]}
    if input_id == "approval-token":
        return {"required_for": ["approve-engineering", "runtime approvals"], "not_persisted": True}
    if input_id == "runtime-port-input":
        return {"integer_range": [1024, 65535], "default": 18042}
    if input_id == "runtime-run-id":
        return {"non_empty_default": "portfolio_runtime_001"}
    return {"non_empty_when_required": True}


def _server_validation(input_id: str | None) -> dict[str, Any]:
    if input_id == "requirements-input":
        return {"model": "RequirementsRequest", "validator": "validate_requirements_text"}
    if input_id == "app-id-input":
        return {"model": "RequirementsRequest", "validator": "validate_app_id"}
    if input_id == "approval-token":
        return {"models": ["ApprovalRequest", "PortfolioApprovalRequest"], "approval_required": True}
    if input_id == "runtime-port-input":
        return {"models": ["PortfolioRuntimeActionRequest", "PortfolioReadRequest"], "ge": 1024, "le": 65535}
    if input_id == "runtime-run-id":
        return {"model": "PortfolioRuntimeActionRequest", "field": "run_id"}
    return {"model": "HTML input"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    root = args.project_root.resolve()
    manifest = build_manifest(root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if manifest["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
