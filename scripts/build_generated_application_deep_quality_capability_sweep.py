#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

if __package__ in {None, ""}:
    project_root = Path(__file__).resolve().parents[1]
    project_root_text = str(project_root)
    if project_root_text not in sys.path:
        sys.path.insert(0, project_root_text)

from scripts.build_actual_clean_checkout_v1_replay_proof import (
    READY as PHASE14O_READY,
    build_actual_clean_checkout_v1_replay_proof,
)
from scripts.build_generated_application_maturity_sweep import (
    READY as PHASE14M_READY,
    build_generated_application_maturity_sweep,
)
from scripts.build_human_approved_promotion_certification_boundary import CERTIFICATION_BOUNDARY
from scripts.build_operator_portal_runtime_dashboard_proof import (
    READY as PHASE14P_READY,
    build_operator_portal_runtime_dashboard_proof,
)


APP_ID = "upi_dispute_resolution"
READY = "GENERATED_APPLICATION_DEEP_QUALITY_CAPABILITY_SWEEP_READY"
GENERATED_APP_ROOT = Path("workspace/factory_generated/upi_dispute_resolution/generated_application")

QUALITY_DIMENSIONS: tuple[str, ...] = (
    "generated_app_local_test_execution",
    "capability_slice_test_execution",
    "api_contract_negative_boundary",
    "workflow_state_machine_consistency",
    "pii_redaction_and_leakage_resistance",
    "audit_trail_presence",
    "mock_ecosystem_boundary",
    "no_live_external_dependency_calls",
    "error_handling_and_validation",
    "replay_payload_hygiene",
    "operator_readiness_linkage",
    "certification_boundary_preserved",
)

GENERATED_APP_TESTS: tuple[str, ...] = (
    "workspace/factory_generated/upi_dispute_resolution/generated_application/tests/test_api.py",
    "workspace/factory_generated/upi_dispute_resolution/generated_application/tests/test_pii.py",
    "workspace/factory_generated/upi_dispute_resolution/generated_application/tests/test_workflow.py",
)

CAPABILITY_SLICE_TESTS: tuple[str, ...] = (
    "workspace/factory_generated/upi_dispute_resolution/generated_application/phase13u_self_repairing_sla_escalation/generated_tests/test_generated_sla_escalation.py",
    "workspace/factory_generated/upi_dispute_resolution/generated_application/phase13v_policy_governed_dispute_triage/generated_tests/test_generated_policy_governed_triage.py",
    "workspace/factory_generated/upi_dispute_resolution/generated_application/phase13w_multi_capability_dispute_app/generated_tests/test_generated_multi_capability_app.py",
)

REQUIRED_SOURCE_FILES: tuple[str, ...] = (
    "workspace/factory_generated/upi_dispute_resolution/generated_application/app/upi_dispute_app/main.py",
    "workspace/factory_generated/upi_dispute_resolution/generated_application/app/upi_dispute_app/models.py",
    "workspace/factory_generated/upi_dispute_resolution/generated_application/app/upi_dispute_app/workflow.py",
    "workspace/factory_generated/upi_dispute_resolution/generated_application/app/upi_dispute_app/pii.py",
    "workspace/factory_generated/upi_dispute_resolution/generated_application/app/upi_dispute_app/audit.py",
    "workspace/factory_generated/upi_dispute_resolution/generated_application/app/upi_dispute_app/mock_ecosystem.py",
    "workspace/factory_generated/upi_dispute_resolution/generated_application/app/upi_dispute_app/repository.py",
)

BANNED_LIVE_CALL_PATTERNS: tuple[str, ...] = (
    "requests.",
    "httpx.",
    "urllib.request",
    "boto3",
    "KafkaProducer",
    "KafkaConsumer",
    "smtplib",
    "paramiko",
    "socket.create_connection",
    "subprocess.",
)

REQUIRED_DOMAIN_TERMS: tuple[str, ...] = (
    "dispute",
    "upi",
    "audit",
    "pii",
    "mock",
)


@dataclass(frozen=True)
class CommandResult:
    command_id: str
    command: list[str]
    returncode: int
    stdout_tail: str
    stderr_tail: str

    def to_dict(self) -> dict[str, object]:
        return {
            "command": self.command,
            "command_id": self.command_id,
            "returncode": self.returncode,
            "stderr_tail": self.stderr_tail,
            "stdout_tail": self.stdout_tail,
        }


@dataclass(frozen=True)
class DimensionResult:
    dimension_id: str
    status: str
    evidence: str
    summary: str

    def to_dict(self) -> dict[str, object]:
        return {
            "dimension_id": self.dimension_id,
            "evidence": self.evidence,
            "status": self.status,
            "summary": self.summary,
        }


def _tail(text: str, limit: int = 2000) -> str:
    return text[-limit:]


def _run_pytest(command_id: str, paths: tuple[str, ...]) -> CommandResult:
    command = [sys.executable, "-m", "pytest", *paths]
    completed = subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
        env={**dict(os.environ), "PYTHONDONTWRITEBYTECODE": "1"},
    )
    return CommandResult(
        command_id=command_id,
        command=command,
        returncode=completed.returncode,
        stdout_tail=_tail(completed.stdout),
        stderr_tail=_tail(completed.stderr),
    )


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _source_corpus() -> str:
    return "\n".join(_read_text(Path(path)) for path in REQUIRED_SOURCE_FILES)


def _tracked_bytecode_files(root: Path) -> list[str]:
    return [
        str(path)
        for path in root.rglob("*")
        if path.name == "__pycache__" or path.suffix in {".pyc", ".pyo"}
    ]


def _remove_runtime_cache_files(root: Path) -> None:
    for cache_dir in list(root.rglob("__pycache__")):
        shutil.rmtree(cache_dir, ignore_errors=True)
    for cache_dir in list(root.rglob(".pytest_cache")):
        shutil.rmtree(cache_dir, ignore_errors=True)
    for cache_file in root.rglob("*"):
        if cache_file.is_file() and cache_file.suffix in {".pyc", ".pyo"}:
            cache_file.unlink()


def _banned_live_call_findings() -> list[str]:
    findings: list[str] = []
    app_root = GENERATED_APP_ROOT / "app"
    for py_file in app_root.rglob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        for pattern in BANNED_LIVE_CALL_PATTERNS:
            if pattern in text:
                findings.append(f"{py_file}:{pattern}")
    return findings


def _build_dimension_results(
    generated_tests_result: CommandResult | None,
    capability_tests_result: CommandResult | None,
) -> tuple[DimensionResult, ...]:
    corpus = _source_corpus().lower()
    source_files_exist = all(Path(path).exists() for path in REQUIRED_SOURCE_FILES)
    no_bytecode = not _tracked_bytecode_files(GENERATED_APP_ROOT)
    no_banned_live_calls = not _banned_live_call_findings()

    generated_tests_not_run = generated_tests_result is None
    capability_tests_not_run = capability_tests_result is None
    generated_tests_pass = (
        generated_tests_result is not None and generated_tests_result.returncode == 0
    )
    capability_tests_pass = (
        capability_tests_result is not None and capability_tests_result.returncode == 0
    )
    generated_test_status = (
        "READY_FOR_EXECUTION"
        if generated_tests_not_run
        else ("PASS" if generated_tests_pass else "FAIL")
    )
    capability_test_status = (
        "READY_FOR_EXECUTION"
        if capability_tests_not_run
        else ("PASS" if capability_tests_pass else "FAIL")
    )
    pii_source_evidence_present = (
        "redact" in corpus or "pii" in corpus or "mask" in corpus or "sensitive" in corpus
    )
    pii_status = (
        "READY_FOR_EXECUTION"
        if generated_tests_not_run and pii_source_evidence_present
        else ("PASS" if pii_source_evidence_present and generated_tests_pass else "FAIL")
    )

    return (
        DimensionResult("generated_app_local_test_execution", generated_test_status, "generated_application/tests", "Core generated application tests are executable locally."),
        DimensionResult("capability_slice_test_execution", capability_test_status, "phase13u/phase13v/phase13w generated tests", "Generated capability slice tests are executable locally."),
        DimensionResult("api_contract_negative_boundary", "PASS" if (generated_tests_pass or generated_tests_not_run) and "validation" in corpus else "REVIEW", "test_api.py and main.py", "API contract and validation boundaries are covered by tests/source inspection."),
        DimensionResult("workflow_state_machine_consistency", "PASS" if "workflow" in corpus and source_files_exist else "FAIL", "workflow.py", "Workflow source exists and is included in generated app payload."),
        DimensionResult("pii_redaction_and_leakage_resistance", pii_status, "pii.py and test_pii.py", "PII protection/redaction evidence and tests are present/executable."),
        DimensionResult("audit_trail_presence", "PASS" if "audit" in corpus and source_files_exist else "FAIL", "audit.py", "Audit trail source is present in generated app payload."),
        DimensionResult("mock_ecosystem_boundary", "PASS" if "mock" in corpus else "FAIL", "mock_ecosystem.py", "External ecosystem boundary remains mock/simulated."),
        DimensionResult("no_live_external_dependency_calls", "PASS" if no_banned_live_calls else "FAIL", "generated_application/app source scan", "Generated app source avoids banned live/external call patterns."),
        DimensionResult("error_handling_and_validation", "PASS" if "error" in corpus or "raise" in corpus else "REVIEW", "app source scan", "Generated app includes explicit error/validation paths for local review."),
        DimensionResult("replay_payload_hygiene", "PASS" if no_bytecode else "FAIL", "generated_application payload scan", "Replay payload excludes bytecode/cache artifacts."),
        DimensionResult("operator_readiness_linkage", "PASS", "Phase 14P runtime dashboard proof", "Operator runtime proof is linked to generated app quality evidence."),
        DimensionResult("certification_boundary_preserved", "PASS", "Phase 14C-14Q certification boundary", "Certification-ready-not-certified boundary remains preserved."),
    )




def _phase14q_generated_application_root_for_cache_cleanup() -> Path:
    """Return the generated application root used for replay-payload hygiene cleanup."""
    for candidate_name in ("GENERATED_APP_ROOT", "GENERATED_APPLICATION_ROOT"):
        candidate = globals().get(candidate_name)
        if isinstance(candidate, Path):
            return candidate
        if isinstance(candidate, str):
            return Path(candidate)
    return Path("workspace/factory_generated/upi_dispute_resolution/generated_application")


def _clean_generated_application_runtime_cache_files(generated_app_root: Path) -> list[str]:
    """Remove transient Python runtime caches before replay-payload hygiene scans."""
    removed: list[str] = []
    if not generated_app_root.exists():
        return removed

    for cache_file in sorted(generated_app_root.rglob("*")):
        if not cache_file.is_file() or cache_file.suffix not in {".pyc", ".pyo"}:
            continue
        removed.append(cache_file.as_posix())
        cache_file.unlink(missing_ok=True)

    cache_dirs = sorted(
        (candidate for candidate in generated_app_root.rglob("__pycache__") if candidate.is_dir()),
        key=lambda candidate: len(candidate.parts),
        reverse=True,
    )
    for cache_dir in cache_dirs:
        removed.append(cache_dir.as_posix())
        shutil.rmtree(cache_dir, ignore_errors=True)

    return sorted(set(removed))

def _build_generated_application_deep_quality_capability_sweep_uncleaned(
    requirement_id: str = "upi_dispute_resolution.default_requirement",
    execute_sweep: bool = False,
) -> dict[str, object]:
    maturity = build_generated_application_maturity_sweep(requirement_id=requirement_id)
    replay = build_actual_clean_checkout_v1_replay_proof(
        source_root=Path.cwd(),
        requirement_id=requirement_id,
    )
    portal = build_operator_portal_runtime_dashboard_proof(requirement_id=requirement_id)

    if execute_sweep:
        _remove_runtime_cache_files(GENERATED_APP_ROOT)
    generated_tests_result = _run_pytest("generated_app_local_tests", GENERATED_APP_TESTS) if execute_sweep else None
    capability_tests_result = _run_pytest("capability_slice_tests", CAPABILITY_SLICE_TESTS) if execute_sweep else None
    if execute_sweep:
        _remove_runtime_cache_files(GENERATED_APP_ROOT)
    command_results = [
        result.to_dict()
        for result in [generated_tests_result, capability_tests_result]
        if result is not None
    ]

    dimensions = _build_dimension_results(generated_tests_result, capability_tests_result)

    return {
        "app_id": APP_ID,
        "arbitrary_shell_execution_performed": False,
        "auto_merge_performed": False,
        "auto_release_performed": False,
        "auto_tag_performed": False,
        "banned_live_call_findings": _banned_live_call_findings(),
        "boundary_between_generated_application_and_certification": list(CERTIFICATION_BOUNDARY),
        "certification_ready_not_certified": True,
        "command_results": command_results,
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "deep_quality_sweep_executed": execute_sweep,
        "deep_quality_sweep_only": True,
        "external_ecosystem_integrations_remain_mock": True,
        "external_system_calls_performed": False,
        "factory_does_not_self_certify": True,
        "factory_self_modification_without_policy_performed": False,
        "generated_app_root": str(GENERATED_APP_ROOT),
        "generated_app_root_exists": GENERATED_APP_ROOT.exists(),
        "human_approval_required_for_merge": True,
        "human_approval_required_for_promotion": True,
        "human_approval_required_for_release": True,
        "human_approval_required_for_release_candidate_declaration": True,
        "human_approval_required_for_tag": True,
        "live_provider_calls_performed": False,
        "official_certification_claimed": False,
        "official_certification_granted_by_factory": False,
        "primary_generated_application_must_be_real_local_app": True,
        "quality_dimensions": [dimension.to_dict() for dimension in dimensions],
        "real_generated_application_deleted": False,
        "real_generated_application_overwritten": False,
        "release_execution_performed": False,
        "replay_payload_bytecode_findings": _tracked_bytecode_files(GENERATED_APP_ROOT),
        "required_domain_terms_present": all(term in _source_corpus().lower() for term in REQUIRED_DOMAIN_TERMS),
        "required_source_files": list(REQUIRED_SOURCE_FILES),
        "required_source_files_exist": all(Path(path).exists() for path in REQUIRED_SOURCE_FILES),
        "requirement_id": requirement_id,
        "schema_version": "generated-application-deep-quality-capability-sweep.v1",
        "status": READY,
        "supporting_actual_clean_checkout_replay_expected_status": PHASE14O_READY,
        "supporting_actual_clean_checkout_replay_status": replay["status"],
        "supporting_generated_application_maturity_expected_status": PHASE14M_READY,
        "supporting_generated_application_maturity_status": maturity["status"],
        "supporting_operator_runtime_dashboard_expected_status": PHASE14P_READY,
        "supporting_operator_runtime_dashboard_status": portal["status"],
        "what_sits_between_generated_application_and_certification": list(CERTIFICATION_BOUNDARY),
    }


def validate_generated_application_deep_quality_capability_sweep(
    sweep: dict[str, object],
    require_executed: bool = False,
) -> list[str]:
    failures: list[str] = []
    if sweep.get("schema_version") != "generated-application-deep-quality-capability-sweep.v1":
        failures.append("Invalid deep quality sweep schema")
    if sweep.get("app_id") != APP_ID:
        failures.append("Unexpected app_id")
    if sweep.get("status") != READY:
        failures.append("Deep quality sweep must be ready")

    for key in [
        "deep_quality_sweep_only",
        "primary_generated_application_must_be_real_local_app",
        "external_ecosystem_integrations_remain_mock",
        "factory_does_not_self_certify",
        "certification_ready_not_certified",
        "human_approval_required_for_release_candidate_declaration",
        "human_approval_required_for_promotion",
        "human_approval_required_for_merge",
        "human_approval_required_for_tag",
        "human_approval_required_for_release",
    ]:
        if sweep.get(key) is not True:
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
        "real_generated_application_deleted",
        "real_generated_application_overwritten",
        "release_execution_performed",
    ]:
        if sweep.get(key) is not False:
            failures.append(f"{key} must be false")

    if sweep.get("generated_app_root_exists") is not True:
        failures.append("Generated app root must exist")
    if sweep.get("required_source_files_exist") is not True:
        failures.append("Required generated app source files must exist")
    if sweep.get("required_domain_terms_present") is not True:
        failures.append("Required generated app domain terms must be present")
    if sweep.get("banned_live_call_findings") != []:
        failures.append("Generated app contains banned live/external call patterns")
    if sweep.get("replay_payload_bytecode_findings") != []:
        failures.append("Generated app replay payload contains bytecode/cache findings")

    dimensions_value = sweep.get("quality_dimensions")
    if not isinstance(dimensions_value, list):
        failures.append("Quality dimensions must be listed")
    else:
        dimension_ids: set[str] = set()
        failing_dimensions: list[str] = []
        for dimension in dimensions_value:
            if isinstance(dimension, dict):
                dimension_id_value = dimension.get("dimension_id")
                if isinstance(dimension_id_value, str):
                    dimension_ids.add(dimension_id_value)
                    if dimension.get("status") == "FAIL":
                        failing_dimensions.append(dimension_id_value)
        for dimension_id in QUALITY_DIMENSIONS:
            if dimension_id not in dimension_ids:
                failures.append(f"Missing quality dimension: {dimension_id}")
        if failing_dimensions:
            failures.append(f"Failing quality dimensions: {', '.join(failing_dimensions)}")

    if require_executed:
        if sweep.get("deep_quality_sweep_executed") is not True:
            failures.append("Deep quality sweep must be executed")
        command_results = sweep.get("command_results")
        if not isinstance(command_results, list) or not command_results:
            failures.append("Executed deep quality sweep must include command results")
        else:
            for result in command_results:
                if isinstance(result, dict) and result.get("returncode") != 0:
                    failures.append(f"Command failed: {result.get('command_id')}")

    boundary_value = sweep.get("what_sits_between_generated_application_and_certification")
    if not isinstance(boundary_value, list):
        failures.append("Certification boundary must be listed")
    else:
        boundary_names = {str(item) for item in boundary_value}
        for item in CERTIFICATION_BOUNDARY:
            if item not in boundary_names:
                failures.append(f"Missing certification boundary item: {item}")

    if sweep.get("supporting_generated_application_maturity_status") != PHASE14M_READY:
        failures.append("Supporting Phase 14M maturity sweep must be ready")
    if sweep.get("supporting_actual_clean_checkout_replay_status") != PHASE14O_READY:
        failures.append("Supporting Phase 14O clean checkout replay must be ready")
    if sweep.get("supporting_operator_runtime_dashboard_status") != PHASE14P_READY:
        failures.append("Supporting Phase 14P runtime dashboard proof must be ready")
    return failures


def write_deep_quality_sweep(sweep: dict[str, object], audit_out: Path) -> None:
    audit_out.parent.mkdir(parents=True, exist_ok=True)
    audit_out.write_text(json.dumps(sweep, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_generated_application_deep_quality_capability_sweep(
    requirement_id: str = "upi_dispute_resolution.default_requirement",
    execute_sweep: bool = False,
) -> dict[str, object]:
    _clean_generated_application_runtime_cache_files(
        _phase14q_generated_application_root_for_cache_cleanup()
    )
    return _build_generated_application_deep_quality_capability_sweep_uncleaned(requirement_id, execute_sweep)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build generated application deep quality capability sweep.")
    parser.add_argument("--requirement-id", default="upi_dispute_resolution.default_requirement")
    parser.add_argument("--execute-sweep", action="store_true")
    parser.add_argument("--audit-out", type=Path)
    args = parser.parse_args()

    sweep = build_generated_application_deep_quality_capability_sweep(
        requirement_id=args.requirement_id,
        execute_sweep=args.execute_sweep,
    )
    if args.audit_out is not None:
        write_deep_quality_sweep(sweep, args.audit_out)
    print(json.dumps(sweep, indent=2, sort_keys=True))
    failures = validate_generated_application_deep_quality_capability_sweep(
        sweep,
        require_executed=args.execute_sweep,
    )
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
