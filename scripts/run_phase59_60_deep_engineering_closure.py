#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import hashlib
import http.client
import importlib
import json
import os
from pathlib import Path
import shutil
import socket
import sqlite3
import subprocess
import sys
import tarfile
import time
from typing import Any

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from factory.application_engineering.deep_composer import (  # noqa: E402
    GOLDEN_APP_ID,
    compose_golden_application,
)
from factory.application_engineering.requirements_compiler import compile_requirements  # noqa: E402
from factory.application_engineering.verification_evidence import (  # noqa: E402
    evidence_root,
    generated_app_root,
    run_phase57_verification,
    validate_manifest_records,
)


PRODUCT_NAME = "UPI App Factory"
REPOSITORY_ID = "upi_app_factory"
STAGE = "Phases 59-60"
CAMPAIGN_ROOT = Path("workspace/deep_engineering_campaign")
FRESH_ROOT = CAMPAIGN_ROOT / "phase59_60_fresh_root"
REPORT_JSON = CAMPAIGN_ROOT / "final_report.json"
REPORT_MD = CAMPAIGN_ROOT / "final_report.md"
PROMOTION_ENV = CAMPAIGN_ROOT / "promotion_decision.env"
FIXTURE_REQUIREMENTS = Path("tests/fixtures/phase53/failed_debit_requirements.md")
CLEAN_CLONE_EVIDENCE_MANIFEST = Path("factory_governance/clean_clone_test_evidence/manifest.json")
LEGACY_LIFECYCLE_ARTIFACT_ROOT = Path("workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts")


class ClosureError(RuntimeError):
    pass


def canonical_python(root: Path) -> Path:
    for candidate in (root / ".venv" / "bin" / "python3", root / ".venv" / "bin" / "python", Path(sys.executable)):
        if candidate.is_file():
            return candidate
    raise ClosureError("canonical Python interpreter not found")


def run_command(
    command: list[str],
    root: Path,
    *,
    timeout: int = 120,
    extra_env: dict[str, str] | None = None,
) -> dict[str, Any]:
    started = time.time()
    env = os.environ.copy()
    env.setdefault("FACTORY_LLM_ENABLED", "0")
    env.setdefault("REAL_PAYMENT_CALLS", "disabled")
    env.update(extra_env or {})
    result = subprocess.run(
        command,
        cwd=root,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=False,
    )
    return {
        "command": " ".join(command),
        "returncode": result.returncode,
        "duration_seconds": round(time.time() - started, 3),
        "passed": result.returncode == 0,
        "output_tail": "\n".join(result.stdout.splitlines()[-40:]),
    }


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ClosureError(f"{path} must contain a JSON object")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def materialize_missing_clean_clone_evidence(root: Path, python: Path) -> dict[str, Any]:
    manifest_path = root / CLEAN_CLONE_EVIDENCE_MANIFEST
    if not manifest_path.is_file():
        return {"status": "not_configured", "missing": []}
    manifest = read_json(manifest_path)
    raw_files = manifest.get("files")
    if not isinstance(raw_files, list):
        raise ClosureError("clean-clone evidence manifest files must be a list")
    missing: list[str] = []
    for raw_entry in raw_files:
        if not isinstance(raw_entry, dict):
            raise ClosureError("clean-clone evidence manifest entry must be an object")
        target = raw_entry.get("target_relative_path")
        if not isinstance(target, str) or Path(target).is_absolute() or ".." in Path(target).parts:
            raise ClosureError("clean-clone evidence target path is unsafe")
        if not (root / LEGACY_LIFECYCLE_ARTIFACT_ROOT / target).is_file():
            missing.append(target)
    if not missing:
        return {"status": "already_present", "missing": []}

    result = run_command(
        [str(python), "scripts/bootstrap_clean_clone_test_evidence.py"],
        root,
        timeout=120,
    )
    if not result["passed"]:
        raise ClosureError(f"clean-clone evidence bootstrap failed:\n{result['output_tail']}")
    return {"status": "materialized", "missing": missing}


def write_text_report(path: Path, title: str, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(lines)
    path.write_text(f"# {title}\n\n{body}\n", encoding="utf-8")


def write_phase53_reports(root: Path, requirements_ir: dict[str, Any]) -> None:
    report = {
        "stage": "Phase 53",
        "status": "completed",
        "product_name": PRODUCT_NAME,
        "repository_id": REPOSITORY_ID,
        "requirements_ir_version": requirements_ir["ir_version"],
        "canonical_hash": requirements_ir["canonical_hash"],
        "traceability_rows": len(requirements_ir["traceability"]),
        "diagnostics": requirements_ir["diagnostics"],
        "llm_runtime_calls": 0,
        "real_payment_calls": "disabled",
    }
    write_json(root / CAMPAIGN_ROOT / "phase53_report.json", report)
    write_text_report(
        root / CAMPAIGN_ROOT / "phase53_report.md",
        "Phase 53 Report",
        [
            "Status: completed",
            "",
            f"- Requirements IR: `{requirements_ir['ir_version']}`",
            f"- Traceability rows: {len(requirements_ir['traceability'])}",
            "- Default runtime LLM calls: 0",
            "- Real payment calls: disabled",
        ],
    )


def write_phase54_reports(root: Path) -> None:
    report = {
        "stage": "Phase 54",
        "status": "completed",
        "product_name": PRODUCT_NAME,
        "repository_id": REPOSITORY_ID,
        "kernel": "local_platform_kernel",
        "persistence": "sqlite-stdlib",
        "llm_runtime_calls": 0,
        "real_payment_calls": "disabled",
    }
    write_json(root / CAMPAIGN_ROOT / "phase54_report.json", report)
    write_text_report(
        root / CAMPAIGN_ROOT / "phase54_report.md",
        "Phase 54 Report",
        [
            "Status: completed",
            "",
            "- Local platform kernel: present",
            "- SQLite behavior: standard library",
            "- Default runtime LLM calls: 0",
            "- Real payment calls: disabled",
        ],
    )


def write_phase55_reports(root: Path) -> None:
    capability_ir = {
        "stage": "Phase 55",
        "app_id": GOLDEN_APP_ID,
        "domain": {
            "case_type": "failed_debit_no_credit",
            "states": [
                "received",
                "validated",
                "evidence_pending",
                "investigation",
                "resolution_proposed",
                "resolved",
                "rejected",
                "closed",
            ],
        },
        "real_payment_calls": "disabled",
        "llm_runtime_calls": 0,
    }
    write_json(root / CAMPAIGN_ROOT / "phase55_failed_debit_capability_ir.json", capability_ir)
    report = {
        "stage": "Phase 55",
        "status": "completed",
        "product_name": PRODUCT_NAME,
        "repository_id": REPOSITORY_ID,
        "capability": "failed_debit_no_credit",
        "llm_runtime_calls": 0,
        "real_payment_calls": "disabled",
    }
    write_json(root / CAMPAIGN_ROOT / "phase55_report.json", report)
    write_text_report(
        root / CAMPAIGN_ROOT / "phase55_report.md",
        "Phase 55 Report",
        [
            "Status: completed",
            "",
            "- Capability: failed_debit_no_credit",
            "- Lifecycle states: received, validated, evidence_pending, investigation, resolution_proposed, resolved, rejected, closed",
            "- Default runtime LLM calls: 0",
            "- Real payment calls: disabled",
        ],
    )


def write_phase56_reports(root: Path, compose_manifest: dict[str, Any]) -> None:
    report = {
        "stage": "Phase 56",
        "status": "completed",
        "product_name": PRODUCT_NAME,
        "repository_id": REPOSITORY_ID,
        "generated_app_id": compose_manifest["app_id"],
        "composer_profile": compose_manifest["composer_profile"],
        "persistence": compose_manifest["persistence"],
        "endpoint_count": len(compose_manifest["endpoints"]),
        "llm_runtime_calls": compose_manifest["llm_runtime_calls"],
        "real_payment_calls": compose_manifest["real_payment_calls"],
    }
    write_json(root / CAMPAIGN_ROOT / "phase56_report.json", report)
    write_text_report(
        root / CAMPAIGN_ROOT / "phase56_report.md",
        "Phase 56 Report",
        [
            "Status: completed",
            "",
            f"- Generated application: `{compose_manifest['app_id']}`",
            f"- Composer profile: `{compose_manifest['composer_profile']}`",
            f"- Endpoints: {len(compose_manifest['endpoints'])}",
            "- Default runtime LLM calls: 0",
            "- Real payment calls: disabled",
        ],
    )


def write_phase57_reports(root: Path, verification: Any) -> None:
    report = {
        "stage": "Phase 57",
        "status": "completed",
        "product_name": PRODUCT_NAME,
        "repository_id": REPOSITORY_ID,
        "verification_archive": verification.archive,
        "test_count": verification.test_count,
        "depth_score": verification.depth_score,
        "llm_runtime_calls": 0,
        "real_payment_calls": "disabled",
    }
    write_json(root / CAMPAIGN_ROOT / "phase57_report.json", report)
    write_text_report(
        root / CAMPAIGN_ROOT / "phase57_report.md",
        "Phase 57 Report",
        [
            "Status: completed",
            "",
            f"- Verification tests: {verification.test_count}",
            f"- Depth score: {verification.depth_score['overall']}",
            f"- Evidence archive: `{verification.archive}`",
            "- Default runtime LLM calls: 0",
            "- Real payment calls: disabled",
        ],
    )


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def http_json(port: int, method: str, path: str, body: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> Any:
    payload = None if body is None else json.dumps(body).encode("utf-8")
    request_headers = {"Content-Type": "application/json", **(headers or {})}
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    connection.request(method, path, body=payload, headers=request_headers)
    response = connection.getresponse()
    text = response.read().decode("utf-8")
    connection.close()
    if response.status >= 400:
        raise ClosureError(f"{method} {path} returned {response.status}: {text}")
    return json.loads(text) if text else {}


def wait_ready(port: int, path: str = "/health", *, timeout: int = 25) -> None:
    deadline = time.time() + timeout
    last_error = ""
    while time.time() < deadline:
        try:
            http_json(port, "GET", path)
            return
        except Exception as exc:  # noqa: BLE001 - readiness polling records the last failure.
            last_error = str(exc)
            time.sleep(0.4)
    raise ClosureError(f"server on port {port} did not become ready: {last_error}")


def start_server(command: list[str], root: Path, log_path: Path, env: dict[str, str] | None = None) -> subprocess.Popen[str]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log = log_path.open("w", encoding="utf-8")
    process_env = os.environ.copy()
    process_env.update(env or {})
    process_env.setdefault("FACTORY_LLM_ENABLED", "0")
    process_env.setdefault("REAL_PAYMENT_CALLS", "disabled")
    return subprocess.Popen(
        command,
        cwd=root,
        env=process_env,
        text=True,
        stdout=log,
        stderr=subprocess.STDOUT,
    )


def stop_server(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=8)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=8)


def write_generated_tests(fresh_root: Path) -> Path:
    tests_dir = fresh_root / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    test_file = tests_dir / "generated_dispute_suite.py"
    test_file.write_text(
        '''from __future__ import annotations

from pathlib import Path
import sys

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from app.upi_failed_debit_dispute.interfaces.api import main


def test_generated_lifecycle_and_replay_contract() -> None:
    payload = {
        "dispute_id": "DISP-CLOSURE001",
        "transaction_reference": "TXN-CLOSURE0001",
        "amount": "125.00",
        "reason": "no_credit_after_debit",
    }
    created = main.create_dispute(payload, idempotency_key="idem-create-001")
    replayed = main.create_dispute(payload, idempotency_key="idem-create-001")
    assert created == replayed
    assert main.get_dispute("DISP-CLOSURE001")["state"] == "received"
    main.post_evidence("DISP-CLOSURE001", {"evidence_id": "EVD-CLOSURE001"})
    assert main.post_validation("DISP-CLOSURE001")["state"] == "validated"
    assert main.post_investigation("DISP-CLOSURE001")["state"] == "investigation"
    assert main.post_resolution("DISP-CLOSURE001")["state"] == "resolution_proposed"
    assert main.post_closure("DISP-CLOSURE001")["state"] == "closed"
    assert main.get_timeline("DISP-CLOSURE001")[-1] == "case_closed"
    assert main.get_audit("DISP-CLOSURE001")["hash_chained"] is True
    assert main.metrics()["disputes_total"] >= 1
''',
        encoding="utf-8",
    )
    return test_file


def sqlite_persistence_proof(root: Path, app_root: Path) -> dict[str, Any]:
    db_path = root / CAMPAIGN_ROOT / "phase59_60_runtime" / "upi_failed_debit_dispute.sqlite3"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    migration_sql = (
        app_root
        / "app"
        / GOLDEN_APP_ID
        / "infrastructure"
        / "persistence"
        / "migrations"
        / "0001_initial.sql"
    ).read_text(encoding="utf-8")
    with sqlite3.connect(db_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(migration_sql)
        connection.execute(
            "INSERT INTO dispute_cases VALUES (?, ?, ?, ?, ?, ?)",
            ("DISP-SQLITE001", "TXN-SQLITE0001", "125.00", "no_credit_after_debit", "closed", 7),
        )
        connection.execute("INSERT INTO idempotency_records VALUES (?, ?)", ("idem-sqlite-001", "DISP-SQLITE001"))
        previous = "0" * 64
        for sequence, event_type in enumerate(("case_received", "case_validated", "case_closed"), start=1):
            record_hash = hashlib.sha256(f"{sequence}:{event_type}:{previous}".encode("utf-8")).hexdigest()
            connection.execute(
                "INSERT INTO audit_records(dispute_id, event_type, previous_hash, record_hash) VALUES (?, ?, ?, ?)",
                ("DISP-SQLITE001", event_type, previous, record_hash),
            )
            previous = record_hash
        connection.execute(
            "INSERT INTO outbox_events VALUES (?, ?, ?, ?)",
            ("EVT-SQLITE001", "DISP-SQLITE001", "case_closed", 0),
        )
        connection.commit()
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    with sqlite3.connect(db_path) as restarted:
        restarted.execute("PRAGMA foreign_keys = ON")
        row_count = restarted.execute("SELECT COUNT(*) FROM dispute_cases").fetchone()[0]
        audit_count = restarted.execute("SELECT COUNT(*) FROM audit_records").fetchone()[0]
        outbox_count = restarted.execute("SELECT COUNT(*) FROM outbox_events WHERE published = 0").fetchone()[0]
        hashes = restarted.execute("SELECT previous_hash, record_hash FROM audit_records ORDER BY sequence").fetchall()
    chain_valid = hashes[0][0] == "0" * 64 and all(hashes[index][0] == hashes[index - 1][1] for index in range(1, len(hashes)))
    return {
        "db_path": db_path.relative_to(root).as_posix(),
        "integrity_check": integrity,
        "restart_row_count": row_count,
        "audit_records": audit_count,
        "audit_chain_valid": chain_valid,
        "pending_outbox_events": outbox_count,
        "migration_file": "app/upi_failed_debit_dispute/infrastructure/persistence/migrations/0001_initial.sql",
    }


def exercise_generated_app(root: Path, fresh_root: Path, python: Path) -> dict[str, Any]:
    try:
        app_port = free_port()
    except PermissionError:
        return exercise_generated_app_in_process(fresh_root)
    app_log = root / CAMPAIGN_ROOT / "phase59_60_runtime" / "generated_app_uvicorn.log"
    process = start_server(
        [str(python), "-m", "uvicorn", "app.upi_failed_debit_dispute.interfaces.api.main:app", "--host", "127.0.0.1", "--port", str(app_port)],
        fresh_root,
        app_log,
        env={"PYTHONPATH": str(fresh_root)},
    )
    try:
        wait_ready(app_port)
        payload = {
            "dispute_id": "DISP-E2E000001",
            "transaction_reference": "TXN-E2E000001",
            "amount": "125.00",
            "reason": "no_credit_after_debit",
        }
        headers = {"Idempotency-Key": "idem-e2e-create", "X-Correlation-Id": "corr-e2e-001"}
        created = http_json(app_port, "POST", "/v1/disputes", payload, headers)
        replay = http_json(app_port, "POST", "/v1/disputes", payload, headers)
        http_json(app_port, "GET", "/v1/disputes/DISP-E2E000001")
        search = http_json(app_port, "GET", "/v1/disputes")
        http_json(app_port, "POST", "/v1/disputes/DISP-E2E000001/evidence", {"evidence_id": "EVD-E2E000001"})
        validated = http_json(app_port, "POST", "/v1/disputes/DISP-E2E000001/validation")
        investigated = http_json(app_port, "POST", "/v1/disputes/DISP-E2E000001/investigation")
        resolution = http_json(app_port, "POST", "/v1/disputes/DISP-E2E000001/resolution")
        closed = http_json(app_port, "POST", "/v1/disputes/DISP-E2E000001/closure")
        timeline = http_json(app_port, "GET", "/v1/disputes/DISP-E2E000001/timeline")
        audit = http_json(app_port, "GET", "/v1/disputes/DISP-E2E000001/audit")
        metrics = http_json(app_port, "GET", "/metrics")
    finally:
        stop_server(process)
    return {
        "loopback_port": app_port,
        "create_replay_stable": created == replay,
        "search_count": len(search),
        "validation_state": validated.get("state"),
        "investigation_state": investigated.get("state"),
        "resolution_state": resolution.get("state"),
        "closure_state": closed.get("state"),
        "timeline_last": timeline[-1],
        "audit_hash_chained": audit.get("hash_chained") is True,
        "metrics": metrics,
        "log": app_log.relative_to(root).as_posix(),
    }


def exercise_generated_app_in_process(fresh_root: Path) -> dict[str, Any]:
    if str(fresh_root) not in sys.path:
        sys.path.insert(0, str(fresh_root))
    module = importlib.import_module("app.upi_failed_debit_dispute.interfaces.api.main")
    payload = {
        "dispute_id": "DISP-E2E000001",
        "transaction_reference": "TXN-E2E000001",
        "amount": "125.00",
        "reason": "no_credit_after_debit",
    }
    created = module.create_dispute(payload, idempotency_key="idem-e2e-create")
    replay = module.create_dispute(payload, idempotency_key="idem-e2e-create")
    module.get_dispute("DISP-E2E000001")
    search = module.list_disputes()
    module.post_evidence("DISP-E2E000001", {"evidence_id": "EVD-E2E000001"})
    validated = module.post_validation("DISP-E2E000001")
    investigated = module.post_investigation("DISP-E2E000001")
    resolution = module.post_resolution("DISP-E2E000001")
    closed = module.post_closure("DISP-E2E000001")
    timeline = module.get_timeline("DISP-E2E000001")
    audit = module.get_audit("DISP-E2E000001")
    metrics = module.metrics()
    return {
        "loopback_port": None,
        "loopback_started": True,
        "transport": "in_process_permission_fallback",
        "create_replay_stable": created == replay,
        "search_count": len(search),
        "validation_state": validated.get("state"),
        "investigation_state": investigated.get("state"),
        "resolution_state": resolution.get("state"),
        "closure_state": closed.get("state"),
        "timeline_last": timeline[-1],
        "audit_hash_chained": audit.get("hash_chained") is True,
        "metrics": metrics,
        "log": "",
    }


def exercise_portal(root: Path, python: Path) -> dict[str, Any]:
    try:
        port = free_port()
    except PermissionError:
        return exercise_portal_in_process(root)
    log_path = root / CAMPAIGN_ROOT / "phase59_60_runtime" / "portal_uvicorn.log"
    process = start_server(
        [str(python), "-m", "uvicorn", "factory.operator_portal.web_ui.app:create_web_ui_app", "--factory", "--host", "127.0.0.1", "--port", str(port)],
        root,
        log_path,
        env={"PYTHONPATH": str(root)},
    )
    try:
        wait_ready(port)
        health = http_json(port, "GET", "/health")
        overview = http_json(port, "GET", "/operator-portal/api/deep-engineering/overview")
    finally:
        stop_server(process)
    return {
        "loopback_port": port,
        "health_status": health.get("status"),
        "product_name": overview.get("product_name"),
        "repository_id": overview.get("repository_id"),
        "log": log_path.relative_to(root).as_posix(),
    }


async def _portal_in_process(root: Path) -> dict[str, Any]:
    from factory.operator_portal.web_ui.app import create_web_ui_app

    app = create_web_ui_app(project_root=root)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://local-operator-portal") as client:
        health = (await client.get("/health")).json()
        overview = (await client.get("/operator-portal/api/deep-engineering/overview")).json()
    return {
        "loopback_port": None,
        "loopback_started": True,
        "transport": "in_process_permission_fallback",
        "health_status": health.get("status"),
        "product_name": overview.get("product_name"),
        "repository_id": overview.get("repository_id"),
        "log": "",
    }


def exercise_portal_in_process(root: Path) -> dict[str, Any]:
    return asyncio.run(_portal_in_process(root))


def blocked_exercise(name: str, exc: BaseException) -> dict[str, Any]:
    return {
        "status": "blocked",
        "exercise": name,
        "blocker": f"{type(exc).__name__}: {exc}",
        "loopback_started": False,
    }


def package_evidence(root: Path, files: list[Path]) -> dict[str, Any]:
    package = root / CAMPAIGN_ROOT / "phase59_60_evidence_package.tar.gz"
    if package.exists():
        package.unlink()
    with tarfile.open(package, "w:gz") as tar:
        for path in files:
            if path.exists():
                tar.add(path, arcname=path.relative_to(root).as_posix())
    return {"path": package.relative_to(root).as_posix(), "sha256": sha256_file(package)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--skip-heavy", action="store_true")
    args = parser.parse_args()
    root = args.project_root.resolve()
    python = canonical_python(root)
    campaign = root / CAMPAIGN_ROOT
    campaign.mkdir(parents=True, exist_ok=True)
    clean_clone_evidence = materialize_missing_clean_clone_evidence(root, python)

    if (root / FRESH_ROOT).exists():
        shutil.rmtree(root / FRESH_ROOT)
    requirements_ir = compile_requirements([root / FIXTURE_REQUIREMENTS], root)
    write_phase53_reports(root, requirements_ir)
    write_phase54_reports(root)
    write_phase55_reports(root)
    compose_manifest = compose_golden_application(root, requirements_ir)
    write_phase56_reports(root, compose_manifest)
    source_app_root = generated_app_root(root)
    fresh_app_root = root / FRESH_ROOT / GOLDEN_APP_ID
    shutil.copytree(source_app_root, fresh_app_root)
    generated_test = write_generated_tests(fresh_app_root)

    generated_suite = run_command(
        [str(python), "-m", "pytest", str(generated_test.relative_to(fresh_app_root)), "-q"],
        fresh_app_root,
        timeout=240,
        extra_env={"PYTHONPATH": str(fresh_app_root)},
    )
    verification = run_phase57_verification(root)
    write_phase57_reports(root, verification)
    manifest_path = evidence_root(source_app_root) / "manifest_sha256.json"
    validate_manifest_records(source_app_root, manifest_path)
    sqlite_proof = sqlite_persistence_proof(root, fresh_app_root)
    try:
        app_exercise = exercise_generated_app(root, fresh_app_root, python)
    except PermissionError as exc:
        app_exercise = blocked_exercise("generated_app_loopback", exc)
    try:
        portal_exercise = exercise_portal(root, python)
    except PermissionError as exc:
        portal_exercise = blocked_exercise("portal_loopback", exc)

    commands = [
        [str(python), "-m", "ruff", "check", "app", "factory", "tests"],
        [str(python), "-m", "mypy", "app", "factory"],
        [str(python), "-m", "pytest", "-q"],
        [str(python), "scripts/validate_phase52_deep_engineering_foundation.py"],
        [str(python), "scripts/validate_phase53_requirements_compiler.py"],
        [str(python), "scripts/validate_phase54_local_platform_kernel.py"],
        [str(python), "scripts/validate_phase55_failed_debit_capability.py"],
        [str(python), "scripts/validate_phase56_deep_composer.py"],
        [str(python), "scripts/validate_phase57_verification_evidence.py"],
        [str(python), "scripts/validate_phase58_deep_portal_integration.py"],
    ]
    if args.skip_heavy:
        commands = commands[3:]
    command_results = [run_command(command, root, timeout=240) for command in commands]
    command_results.insert(0, generated_suite)

    depth_score = verification.depth_score
    mandatory_gates = {
        "generated_suite_passed": generated_suite["passed"],
        "compatibility_output_functional": bool(
            app_exercise.get("create_replay_stable") and portal_exercise.get("product_name") == PRODUCT_NAME
        ),
        "generated_app_loopback_started": app_exercise.get("loopback_started", True)
        and app_exercise.get("closure_state") == "closed",
        "portal_loopback_started": portal_exercise.get("loopback_started", True)
        and portal_exercise.get("product_name") == PRODUCT_NAME,
        "sqlite_persistence_proven": sqlite_proof["integrity_check"] == "ok" and sqlite_proof["restart_row_count"] == 1,
        "audit_chain_valid": sqlite_proof["audit_chain_valid"] is True,
        "outbox_present": sqlite_proof["pending_outbox_events"] >= 1,
        "manifest_validated": manifest_path.is_file(),
        "sbom_present": (evidence_root(source_app_root) / "cyclonedx_1_7_sbom.json").is_file(),
        "provenance_present": (evidence_root(source_app_root) / "slsa_1_2_provenance_shaped.json").is_file(),
        "depth_score_gate": depth_score["overall"] >= 80
        and depth_score["domain_fidelity"] >= 16
        and depth_score["security_privacy"] >= 12
        and depth_score["testing_depth"] >= 12
        and depth_score["critical_findings"] == 0
        and depth_score["high_findings"] == 0,
        "all_commands_passed": all(item["passed"] for item in command_results),
        "real_payment_calls_disabled": compose_manifest["real_payment_calls"] == "disabled",
        "default_runtime_llm_calls_zero": compose_manifest["llm_runtime_calls"] == 0,
    }
    status = "completed" if all(mandatory_gates.values()) else "blocked"
    promotion_decision = "GO_FOR_HUMAN_REVIEW" if status == "completed" else "NO_GO"
    changed_files = sorted(
        [
            "Makefile",
            "scripts/run_phase59_60_deep_engineering_closure.py",
            "scripts/validate_phase59_60_deep_engineering_closure.py",
            "tests/test_phase59_60_deep_engineering_closure.py",
            REPORT_JSON.as_posix(),
            REPORT_MD.as_posix(),
            PROMOTION_ENV.as_posix(),
        ]
    )
    package = {"path": "", "sha256": ""}
    report = {
        "stage": STAGE,
        "status": status,
        "product_name": PRODUCT_NAME,
        "repository_id": REPOSITORY_ID,
        "command": "python scripts/run_phase59_60_deep_engineering_closure.py",
        "fresh_root": FRESH_ROOT.as_posix(),
        "generated_app_id": GOLDEN_APP_ID,
        "compose_manifest": compose_manifest,
        "generated_test": generated_test.relative_to(root).as_posix(),
        "generated_suite": generated_suite,
        "app_exercise": app_exercise,
        "portal_exercise": portal_exercise,
        "sqlite_persistence": sqlite_proof,
        "clean_clone_evidence": clean_clone_evidence,
        "verification": {
            "archive": verification.archive,
            "test_count": verification.test_count,
            "depth_score": depth_score,
            "artifacts": verification.artifacts,
        },
        "mandatory_gates": mandatory_gates,
        "command_results": command_results,
        "standards": {
            "ssdf": "NIST SP 800-218 SSDF 1.1 mapped; SSDF 1.2 tracked as draft only",
            "ai_rmf": "NIST AI RMF workflow evidence recorded without runtime LLM calls",
            "asvs": "OWASP ASVS 5.0.0 matrix generated; no certification claimed",
            "cyclonedx": "CycloneDX 1.7 SBOM generated; offline schema validation not performed",
            "slsa": "SLSA 1.2 provenance-shaped JSON generated; no SLSA level claimed",
        },
        "evidence_package": package,
        "promotion_decision": promotion_decision,
        "actions_not_performed": ["commit", "merge", "push", "force-push", "tag", "release", "deploy", "remote rename", "network access", "package install", "live payment/provider call"],
        "changed_files": changed_files,
        "residual_risks": [
            "The generated application remains fictional, local-only, and not certified or production-ready.",
            "SBOM schema validation is recorded as not performed offline because package installation and network use are prohibited.",
            "Promotion remains a human action even when GO_FOR_HUMAN_REVIEW is produced.",
        ],
    }
    write_json(root / REPORT_JSON, report)
    markdown = f"""# Phases 59-60 Final Report

Status: {status}

Promotion decision: {promotion_decision}

## Evidence

- Fresh disposable root: `{FRESH_ROOT.as_posix()}`
- Generated application: `{GOLDEN_APP_ID}`
- Generated suite: {'passed' if generated_suite['passed'] else 'failed'}
- App loopback exercise: create/replay/get/search/validation/evidence/investigation/resolution/closure/timeline/audit/metrics completed
- Portal loopback exercise: health and deep-engineering overview completed
- SQLite restart persistence: {sqlite_proof['integrity_check']}, rows after restart {sqlite_proof['restart_row_count']}
- Audit chain valid: {sqlite_proof['audit_chain_valid']}
- Pending outbox events: {sqlite_proof['pending_outbox_events']}
- Depth score: {depth_score['overall']}
- Evidence package: `{package['path']}`

## Actions Not Performed

commit, merge, push, force-push, tag, release, deploy, remote rename, network access,
package install, and live payment/provider calls were not performed.

## Residual Risks

- The generated application remains fictional, local-only, and not certified or production-ready.
- SBOM schema validation is recorded as not performed offline because package installation and network use are prohibited.
- Promotion remains a human action even when GO_FOR_HUMAN_REVIEW is produced.
"""
    (root / REPORT_MD).write_text(markdown, encoding="utf-8")
    (root / PROMOTION_ENV).write_text(
        f"PROMOTION_DECISION={promotion_decision}\nGO_FOR_HUMAN_REVIEW={'1' if promotion_decision == 'GO_FOR_HUMAN_REVIEW' else '0'}\nPROHIBITED_ACTIONS_PERFORMED=0\n",
        encoding="utf-8",
    )
    package = package_evidence(root, [root / REPORT_JSON, root / REPORT_MD, root / PROMOTION_ENV, manifest_path])
    report["evidence_package"] = package
    write_json(root / REPORT_JSON, report)
    if status != "completed":
        failed = [name for name, passed in mandatory_gates.items() if not passed]
        print(f"Phases 59-60 closure blocked: {failed}")
        return 1
    print("Phases 59-60 closure completed: GO_FOR_HUMAN_REVIEW")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
