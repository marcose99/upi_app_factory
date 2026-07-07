#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import ClassVar
from urllib.request import urlopen

if __package__ in {None, ""}:
    project_root = Path(__file__).resolve().parents[1]
    project_root_text = str(project_root)
    if project_root_text not in sys.path:
        sys.path.insert(0, project_root_text)

from scripts.build_actual_clean_checkout_v1_replay_proof import (
    READY as PHASE14O_READY,
    build_actual_clean_checkout_v1_replay_proof,
)
from scripts.build_human_approved_promotion_certification_boundary import CERTIFICATION_BOUNDARY
from scripts.build_operator_portal_certification_dashboard_integration import (
    READY as PHASE14L_READY,
    build_operator_portal_certification_dashboard_integration,
)


APP_ID = "upi_dispute_resolution"
READY = "OPERATOR_PORTAL_RUNTIME_DASHBOARD_PROOF_READY"

RUNTIME_ROUTES: tuple[str, ...] = (
    "/dashboards/certification-readiness",
    "/api/dashboards/certification-readiness",
    "/api/certification-readiness",
    "/health",
)

OPERATOR_VISIBLE_WORDING: tuple[str, ...] = (
    "Certification-ready, not certified.",
    "Factory does not self-certify.",
    "Official certification decision remains with authorized certifying authorities.",
    "External ecosystem integrations remain mock or simulated.",
)

DASHBOARD_CARDS: tuple[str, ...] = (
    "certification_boundary",
    "evidence_pack",
    "fresh_recipient_replay",
    "actual_clean_checkout_replay",
    "operator_runtime_probe",
    "official_decision_boundary",
    "safety_controls",
)


@dataclass(frozen=True)
class RuntimeProbeResult:
    route: str
    status_code: int
    content_type: str
    contains_required_wording: bool
    response_excerpt: str

    def to_dict(self) -> dict[str, object]:
        return {
            "contains_required_wording": self.contains_required_wording,
            "content_type": self.content_type,
            "response_excerpt": self.response_excerpt,
            "route": self.route,
            "status_code": self.status_code,
        }


def build_dashboard_payload(requirement_id: str) -> dict[str, object]:
    return {
        "app_id": APP_ID,
        "cards": list(DASHBOARD_CARDS),
        "certification_ready_not_certified": True,
        "external_ecosystem_integrations_remain_mock": True,
        "factory_does_not_self_certify": True,
        "mode": "OPERATOR_PORTAL_RUNTIME_DASHBOARD_PROOF",
        "official_certification_claimed": False,
        "official_certification_granted_by_factory": False,
        "operator_visible_wording": list(OPERATOR_VISIBLE_WORDING),
        "release_execution_performed": False,
        "requirement_id": requirement_id,
        "status": READY,
        "what_sits_between_generated_application_and_certification": list(CERTIFICATION_BOUNDARY),
    }


class CertificationReadinessDashboardHandler(BaseHTTPRequestHandler):
    payload: ClassVar[dict[str, object]] = {}

    def log_message(self, format: str, *args: object) -> None:
        return

    def _write_response(self, status_code: int, content_type: str, body: str) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:
        route = self.path.split("?", 1)[0]
        if route == "/health":
            self._write_response(
                200,
                "application/json",
                json.dumps({"status": "ok", "dashboard": READY}, sort_keys=True),
            )
            return

        if route in {"/api/dashboards/certification-readiness", "/api/certification-readiness"}:
            self._write_response(
                200,
                "application/json",
                json.dumps(self.payload, indent=2, sort_keys=True),
            )
            return

        if route == "/dashboards/certification-readiness":
            wording_items = "\n".join(
                f"<li>{phrase}</li>" for phrase in OPERATOR_VISIBLE_WORDING
            )
            cards = "\n".join(f"<li>{card}</li>" for card in DASHBOARD_CARDS)
            html = (
                "<!doctype html>\n"
                "<html lang=\"en\">\n"
                "<head><title>Certification Readiness Dashboard</title></head>\n"
                "<body>\n"
                "<h1>Certification Readiness Dashboard</h1>\n"
                "<p>Certification-ready, not certified.</p>\n"
                "<p>Factory does not self-certify.</p>\n"
                "<p>Official certification decision remains with authorized certifying authorities.</p>\n"
                "<p>External ecosystem integrations remain mock or simulated.</p>\n"
                "<h2>Operator Visible Wording</h2>\n"
                f"<ul>{wording_items}</ul>\n"
                "<h2>Dashboard Cards</h2>\n"
                f"<ul>{cards}</ul>\n"
                "</body>\n"
                "</html>\n"
            )
            self._write_response(200, "text/html; charset=utf-8", html)
            return

        self._write_response(404, "text/plain; charset=utf-8", "Not found")


def _response_excerpt(text: str, limit: int = 1200) -> str:
    return text[:limit]


def _contains_required_wording(route: str, body: str) -> bool:
    if route == "/health":
        return READY in body
    return all(phrase in body for phrase in OPERATOR_VISIBLE_WORDING)


def execute_runtime_probe(requirement_id: str) -> tuple[RuntimeProbeResult, ...]:
    CertificationReadinessDashboardHandler.payload = build_dashboard_payload(requirement_id)
    server = HTTPServer(("127.0.0.1", 0), CertificationReadinessDashboardHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        results: list[RuntimeProbeResult] = []
        for route in RUNTIME_ROUTES:
            url = f"http://127.0.0.1:{port}{route}"
            with urlopen(url, timeout=5) as response:
                status_code = int(response.status)
                content_type = response.headers.get("Content-Type", "")
                body = response.read().decode("utf-8")
            results.append(
                RuntimeProbeResult(
                    route=route,
                    status_code=status_code,
                    content_type=content_type,
                    contains_required_wording=_contains_required_wording(route, body),
                    response_excerpt=_response_excerpt(body),
                )
            )
        return tuple(results)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def build_operator_portal_runtime_dashboard_proof(
    requirement_id: str = "upi_dispute_resolution.default_requirement",
    execute_probe: bool = False,
) -> dict[str, object]:
    portal_integration = build_operator_portal_certification_dashboard_integration(
        requirement_id=requirement_id
    )
    replay_proof = build_actual_clean_checkout_v1_replay_proof(
        source_root=Path.cwd(),
        execute_replay=False,
        requirement_id=requirement_id,
    )
    probe_results = execute_runtime_probe(requirement_id) if execute_probe else ()

    return {
        "app_id": APP_ID,
        "arbitrary_shell_execution_performed": False,
        "auto_merge_performed": False,
        "auto_release_performed": False,
        "auto_tag_performed": False,
        "boundary_between_generated_application_and_certification": list(CERTIFICATION_BOUNDARY),
        "certification_ready_not_certified": True,
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "dashboard_cards": list(DASHBOARD_CARDS),
        "external_ecosystem_integrations_remain_mock": True,
        "external_system_calls_performed": False,
        "factory_does_not_self_certify": True,
        "factory_self_modification_without_policy_performed": False,
        "human_approval_required_for_merge": True,
        "human_approval_required_for_promotion": True,
        "human_approval_required_for_release": True,
        "human_approval_required_for_release_candidate_declaration": True,
        "human_approval_required_for_tag": True,
        "live_provider_calls_performed": False,
        "official_certification_claimed": False,
        "official_certification_granted_by_factory": False,
        "operator_visible_status_must_be_not_certified": True,
        "operator_visible_wording": list(OPERATOR_VISIBLE_WORDING),
        "real_generated_application_deleted": False,
        "real_generated_application_overwritten": False,
        "portal_runtime_probe_performed": execute_probe,
        "release_execution_performed": False,
        "requirement_id": requirement_id,
        "runtime_probe_results": [result.to_dict() for result in probe_results],
        "runtime_routes": list(RUNTIME_ROUTES),
        "schema_version": "operator-portal-runtime-dashboard-proof.v1",
        "status": READY,
        "supporting_actual_clean_checkout_replay_expected_status": PHASE14O_READY,
        "supporting_actual_clean_checkout_replay_status": replay_proof["status"],
        "supporting_portal_integration_expected_status": PHASE14L_READY,
        "supporting_portal_integration_status": portal_integration["status"],
        "what_sits_between_generated_application_and_certification": list(CERTIFICATION_BOUNDARY),
    }


def validate_operator_portal_runtime_dashboard_proof(
    proof: dict[str, object],
    require_executed: bool = False,
) -> list[str]:
    failures: list[str] = []
    if proof.get("schema_version") != "operator-portal-runtime-dashboard-proof.v1":
        failures.append("Invalid operator portal runtime dashboard proof schema")
    if proof.get("app_id") != APP_ID:
        failures.append("Unexpected app_id")
    if proof.get("status") != READY:
        failures.append("Operator portal runtime dashboard proof must be ready")

    for key in [
        "operator_visible_status_must_be_not_certified",
        "external_ecosystem_integrations_remain_mock",
        "factory_does_not_self_certify",
        "certification_ready_not_certified",
        "human_approval_required_for_release_candidate_declaration",
        "human_approval_required_for_promotion",
        "human_approval_required_for_merge",
        "human_approval_required_for_tag",
        "human_approval_required_for_release",
    ]:
        if proof.get(key) is not True:
            failures.append(f"{key} must be true")

    for key in [
        "arbitrary_shell_execution_performed",
        "auto_merge_performed",
        "auto_tag_performed",
        "auto_release_performed",
        "external_system_calls_performed",
        "factory_self_modification_without_policy_performed",
        "live_provider_calls_performed",
        "official_certification_claimed",
        "official_certification_granted_by_factory",
        "release_execution_performed",
    ]:
        if proof.get(key) is not False:
            failures.append(f"{key} must be false")

    if require_executed and proof.get("portal_runtime_probe_performed") is not True:
        failures.append("Portal runtime probe must be executed")

    routes_value = proof.get("runtime_routes")
    if not isinstance(routes_value, list):
        failures.append("Runtime routes must be listed")
    else:
        route_names = {str(item) for item in routes_value}
        for route in RUNTIME_ROUTES:
            if route not in route_names:
                failures.append(f"Missing runtime route: {route}")

    wording_value = proof.get("operator_visible_wording")
    if not isinstance(wording_value, list):
        failures.append("Operator visible wording must be listed")
    else:
        wording_names = {str(item) for item in wording_value}
        for phrase in OPERATOR_VISIBLE_WORDING:
            if phrase not in wording_names:
                failures.append(f"Missing operator wording: {phrase}")

    if require_executed:
        probe_results_value = proof.get("runtime_probe_results")
        if not isinstance(probe_results_value, list) or not probe_results_value:
            failures.append("Executed proof must include runtime probe results")
        else:
            probed_routes: set[str] = set()
            for result in probe_results_value:
                if isinstance(result, dict):
                    result_route_value = result.get("route")
                    result_route = (
                        result_route_value if isinstance(result_route_value, str) else "<unknown>"
                    )
                    if isinstance(result_route_value, str):
                        probed_routes.add(result_route_value)
                    if result.get("status_code") != 200:
                        failures.append(f"Runtime route did not return 200: {result_route}")
                    if result.get("contains_required_wording") is not True:
                        failures.append(f"Runtime route missing required wording: {result_route}")
            for route in RUNTIME_ROUTES:
                if route not in probed_routes:
                    failures.append(f"Missing runtime probe result for route: {route}")

    boundary_value = proof.get("what_sits_between_generated_application_and_certification")
    if not isinstance(boundary_value, list):
        failures.append("Certification boundary must be listed")
    else:
        boundary_names = {str(item) for item in boundary_value}
        for item in CERTIFICATION_BOUNDARY:
            if item not in boundary_names:
                failures.append(f"Missing certification boundary item: {item}")

    if proof.get("supporting_portal_integration_status") != PHASE14L_READY:
        failures.append("Supporting Phase 14L portal integration must be ready")
    if proof.get("supporting_actual_clean_checkout_replay_status") != PHASE14O_READY:
        failures.append("Supporting Phase 14O replay proof must be ready")
    return failures


def write_runtime_dashboard_proof(proof: dict[str, object], audit_out: Path) -> None:
    audit_out.parent.mkdir(parents=True, exist_ok=True)
    audit_out.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build operator portal runtime dashboard proof.")
    parser.add_argument("--requirement-id", default="upi_dispute_resolution.default_requirement")
    parser.add_argument("--execute-runtime-probe", action="store_true")
    parser.add_argument("--audit-out", type=Path)
    args = parser.parse_args()

    proof = build_operator_portal_runtime_dashboard_proof(
        requirement_id=args.requirement_id,
        execute_probe=args.execute_runtime_probe,
    )
    if args.audit_out is not None:
        write_runtime_dashboard_proof(proof, args.audit_out)
    print(json.dumps(proof, indent=2, sort_keys=True))
    failures = validate_operator_portal_runtime_dashboard_proof(
        proof,
        require_executed=args.execute_runtime_probe,
    )
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
