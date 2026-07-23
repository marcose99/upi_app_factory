#!/usr/bin/env python3
"""Drive the governed public clean-clone recipient journey through portal HTTP APIs."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Any, Sequence
from urllib import error, request


ENGINEERING_APPROVAL_TOKEN = "APPROVE_PORTAL_APPLICATION_ENGINEERING"
PORTFOLIO_APPROVAL_TOKEN = "phase51-local-portfolio-approval"


class E2EError(RuntimeError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True, help="Local operator portal base URL.")
    parser.add_argument("--requirements", required=True, type=Path, help="Requirements Markdown file.")
    parser.add_argument("--evidence-root", required=True, type=Path, help="Local directory for e2e proof JSON.")
    parser.add_argument("--json-output", required=True, type=Path, help="Machine-readable proof output path.")
    return parser.parse_args(argv)


def _url(base_url: str, path: str) -> str:
    return base_url.rstrip("/") + "/" + path.lstrip("/")


def _http_json(base_url: str, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload, sort_keys=True).encode("utf-8")
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = request.Request(_url(base_url, path), data=body, headers=headers, method=method.upper())
    try:
        with request.urlopen(req, timeout=15) as response:
            data = response.read(2 * 1024 * 1024)
            status = response.status
    except error.HTTPError as exc:
        detail = exc.read(128 * 1024).decode("utf-8", errors="replace")
        raise E2EError(f"{method} {path} failed with HTTP {exc.code}: {detail[:1000]}") from exc
    except OSError as exc:
        raise E2EError(f"{method} {path} failed: {exc}") from exc
    try:
        value = json.loads(data.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise E2EError(f"{method} {path} returned non-JSON HTTP {status}") from exc
    if not isinstance(value, dict):
        raise E2EError(f"{method} {path} returned a non-object JSON payload")
    return value


def _http_bytes(base_url: str, path: str) -> dict[str, Any]:
    req = request.Request(_url(base_url, path), headers={"Accept": "application/octet-stream"}, method="GET")
    try:
        with request.urlopen(req, timeout=30) as response:
            data = response.read(25 * 1024 * 1024)
            status = response.status
    except error.HTTPError as exc:
        detail = exc.read(128 * 1024).decode("utf-8", errors="replace")
        raise E2EError(f"GET {path} failed with HTTP {exc.code}: {detail[:1000]}") from exc
    return {"http_status": status, "size_bytes": len(data), "sha256": _sha256_bytes(data)}


def _poll_run(base_url: str, run_id: str) -> dict[str, Any]:
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        run = _http_json(base_url, "GET", f"/operator-portal/api/runs/{run_id}")
        if run.get("state") in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            return run
        time.sleep(0.5)
    raise E2EError(f"run {run_id} did not reach a terminal state")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run(argv: Sequence[str] | None = None) -> dict[str, Any]:
    args = _parse_args(argv)
    requirements_path = args.requirements.expanduser().resolve()
    requirements = requirements_path.read_text(encoding="utf-8")
    requirements_sha256 = _sha256_bytes(requirements.encode("utf-8"))
    app_id = os.getenv("UPI_APP_FACTORY_PUBLIC_E2E_APP_ID", "upi_failed_debit_no_credit")
    runtime_run_id = "public_e2e_runtime_" + requirements_sha256[:12]
    runtime_port = int(os.getenv("UPI_APP_FACTORY_PUBLIC_E2E_RUNTIME_PORT", "18042"))
    proof: dict[str, Any] = {
        "schema_version": "public-clean-clone-recipient-e2e.v1",
        "started_at_utc": _utc_now(),
        "base_url": args.base_url,
        "requirements_path": str(requirements_path),
        "requirements_sha256": requirements_sha256,
        "app_id": app_id,
        "runtime_run_id": runtime_run_id,
        "runtime_port": runtime_port,
        "steps": {},
        "mock_boundary": True,
        "real_payment_calls": "disabled",
        "default_llm_calls": 0,
        "certification_posture": "certification-ready-not-certified",
    }
    stop_payload: dict[str, Any] | None = None
    runtime_started: dict[str, Any] | None = None
    try:
        proof["steps"]["health"] = _http_json(args.base_url, "GET", "/health")
        proof["steps"]["validate"] = _http_json(
            args.base_url,
            "POST",
            "/operator-portal/api/requirements/validate",
            {"requirements": requirements, "app_id": app_id},
        )
        created = _http_json(
            args.base_url,
            "POST",
            "/operator-portal/api/runs",
            {"requirements": requirements, "app_id": app_id},
        )
        run_id = str(created["run_id"])
        proof["run_id"] = run_id
        proof["steps"]["create_run"] = created
        proof["steps"]["plan"] = _http_json(args.base_url, "POST", f"/operator-portal/api/runs/{run_id}/plan")
        proof["steps"]["engineering_approval"] = _http_json(
            args.base_url,
            "POST",
            f"/operator-portal/api/runs/{run_id}/approvals",
            {
                "actor": "public-clean-clone-recipient-e2e",
                "approval_token": os.getenv("UPI_APP_FACTORY_PORTAL_APPROVAL_TOKEN", ENGINEERING_APPROVAL_TOKEN),
            },
        )
        proof["steps"]["execute"] = _http_json(args.base_url, "POST", f"/operator-portal/api/runs/{run_id}/execute")
        terminal = _poll_run(args.base_url, run_id)
        proof["steps"]["terminal_run"] = terminal
        proof["steps"]["events"] = _http_json(args.base_url, "GET", f"/operator-portal/api/runs/{run_id}/events")
        proof["steps"]["validation"] = _http_json(args.base_url, "GET", f"/operator-portal/api/runs/{run_id}/validation")
        proof["steps"]["governance_evidence"] = _http_json(args.base_url, "GET", f"/operator-portal/api/runs/{run_id}/evidence")
        proof["steps"]["application_download"] = _http_bytes(args.base_url, f"/operator-portal/api/runs/{run_id}/downloads/application")
        proof["steps"]["evidence_download"] = _http_bytes(args.base_url, f"/operator-portal/api/runs/{run_id}/downloads/evidence")

        result = terminal.get("engineering_result")
        if not isinstance(result, dict):
            raise E2EError("terminal run did not include engineering_result")
        registration = result.get("portfolio_registration")
        if not isinstance(registration, dict):
            raise E2EError("terminal run did not include portfolio registration")
        version_id = str(registration["version_id"])
        proof["version_id"] = version_id
        proof["version_identity_sha256"] = registration.get("version_identity_sha256")
        proof["tests_present"] = result.get("tests_present")
        proof["tests_executed"] = result.get("tests_executed")
        proof["generated_test_execution"] = result.get("generated_test_execution")
        proof["openapi_inventory"] = result.get("openapi_inventory")

        proof["steps"]["portfolio_catalogue"] = _http_json(args.base_url, "GET", "/operator-portal/api/portfolio/catalogue")
        proof["steps"]["portfolio_openapi"] = _http_json(
            args.base_url,
            "POST",
            "/operator-portal/api/portfolio/runtime/openapi",
            {"app_id": app_id, "version_id": version_id},
        )
        start_approval = _http_json(
            args.base_url,
            "POST",
            "/operator-portal/api/portfolio/approvals",
            {
                "action": "start",
                "scope": runtime_run_id,
                "actor": "public-clean-clone-recipient-e2e",
                "approval_token": os.getenv("UPI_APP_FACTORY_PORTFOLIO_APPROVAL_TOKEN", PORTFOLIO_APPROVAL_TOKEN),
            },
        )
        proof["steps"]["runtime_start_approval"] = start_approval
        runtime_request = {
            "app_id": app_id,
            "version_id": version_id,
            "run_id": runtime_run_id,
            "port": runtime_port,
            "approval_nonce": start_approval["nonce"],
        }
        proof["steps"]["runtime_start"] = _http_json(args.base_url, "POST", "/operator-portal/api/portfolio/runtime/start", runtime_request)
        runtime_started = runtime_request
        read_request = {key: runtime_request[key] for key in ("app_id", "version_id", "run_id", "port")}
        proof["steps"]["runtime_status"] = _http_json(args.base_url, "POST", "/operator-portal/api/portfolio/runtime/status", read_request)
        proof["steps"]["runtime_scenarios"] = _http_json(args.base_url, "POST", "/operator-portal/api/portfolio/scenarios", read_request)
        proof["steps"]["runtime_logs"] = _http_json(args.base_url, "POST", "/operator-portal/api/portfolio/runtime/logs", read_request)
        proof["steps"]["runtime_metrics"] = _http_json(args.base_url, "POST", "/operator-portal/api/portfolio/runtime/metrics", read_request)
        proof["steps"]["portfolio_evidence"] = _http_json(args.base_url, "GET", "/operator-portal/api/portfolio/evidence")
        stop_approval = _http_json(
            args.base_url,
            "POST",
            "/operator-portal/api/portfolio/approvals",
            {
                "action": "stop",
                "scope": runtime_run_id,
                "actor": "public-clean-clone-recipient-e2e",
                "approval_token": os.getenv("UPI_APP_FACTORY_PORTFOLIO_APPROVAL_TOKEN", PORTFOLIO_APPROVAL_TOKEN),
            },
        )
        stop_payload = {
            **runtime_request,
            "approval_nonce": stop_approval["nonce"],
        }
        proof["steps"]["runtime_stop_approval"] = stop_approval
        proof["steps"]["runtime_stop"] = _http_json(args.base_url, "POST", "/operator-portal/api/portfolio/runtime/stop", stop_payload)
        stop_payload = None
        runtime_started = None
        validation = proof["steps"]["validation"]
        proof["status"] = "passed" if validation.get("decision") == "GO" and terminal.get("final_decision") == "GO" else "failed"
        if proof["status"] != "passed":
            raise E2EError("portal journey did not produce a validation-derived GO")
        return proof
    except Exception as exc:
        proof["status"] = "failed"
        proof["error"] = str(exc)
        raise
    finally:
        if stop_payload is None and runtime_started is not None:
            try:
                stop_approval = _http_json(
                    args.base_url,
                    "POST",
                    "/operator-portal/api/portfolio/approvals",
                    {
                        "action": "stop",
                        "scope": runtime_run_id,
                        "actor": "public-clean-clone-recipient-e2e",
                        "approval_token": os.getenv("UPI_APP_FACTORY_PORTFOLIO_APPROVAL_TOKEN", PORTFOLIO_APPROVAL_TOKEN),
                    },
                )
                stop_payload = {**runtime_started, "approval_nonce": stop_approval["nonce"]}
                proof["steps"]["runtime_stop_final_approval"] = stop_approval
            except Exception as exc:
                proof["runtime_stop_final_approval_error"] = str(exc)
        if stop_payload is not None:
            try:
                proof["steps"].setdefault(
                    "runtime_stop_final",
                    _http_json(args.base_url, "POST", "/operator-portal/api/portfolio/runtime/stop", stop_payload),
                )
            except Exception as exc:
                proof["runtime_stop_final_error"] = str(exc)
        proof["completed_at_utc"] = _utc_now()
        proof["proof_sha256"] = _sha256_bytes(
            json.dumps({key: value for key, value in proof.items() if key != "proof_sha256"}, sort_keys=True).encode("utf-8")
        )
        args.evidence_root.mkdir(parents=True, exist_ok=True)
        _write_json(args.evidence_root / "public_clean_clone_recipient_e2e_proof.json", proof)
        _write_json(args.json_output, proof)


def main(argv: Sequence[str] | None = None) -> int:
    try:
        proof = run(argv)
    except Exception as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, indent=2, sort_keys=True))
        return 2
    print(json.dumps(proof, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
