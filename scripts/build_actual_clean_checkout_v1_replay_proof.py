#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

if __package__ in {None, ""}:
    project_root = Path(__file__).resolve().parents[1]
    project_root_text = str(project_root)
    if project_root_text not in sys.path:
        sys.path.insert(0, project_root_text)

from scripts.build_human_approved_promotion_certification_boundary import CERTIFICATION_BOUNDARY
from scripts.build_v1_release_candidate_replay_gate import (
    READY as PHASE14N_READY,
    build_v1_release_candidate_replay_gate,
)


APP_ID = "upi_dispute_resolution"
READY = "ACTUAL_CLEAN_CHECKOUT_V1_REPLAY_PROOF_READY"
DEFAULT_CHECKOUT_REF = "v0.14.13-v1-release-candidate-replay-gate"

REPLAY_STEPS: tuple[str, ...] = (
    "create_temp_replay_workspace",
    "git_clone_local_repository",
    "checkout_replay_capable_candidate_ref",
    "verify_clean_checkout_status",
    "verify_python_310_runtime",
    "validate_phase14n_replay_gate",
    "run_phase14n_targeted_tests",
    "run_generated_application_tests",
    "build_replay_gate_evidence_from_checkout",
    "emit_actual_replay_proof",
)

GENERATED_APP_TEST_PATHS: tuple[str, ...] = (
    "workspace/factory_generated/upi_dispute_resolution/generated_application/tests/test_api.py",
    "workspace/factory_generated/upi_dispute_resolution/generated_application/tests/test_pii.py",
    "workspace/factory_generated/upi_dispute_resolution/generated_application/tests/test_workflow.py",
)


@dataclass(frozen=True)
class CommandResult:
    command_id: str
    command: list[str]
    cwd: str
    returncode: int
    stdout_tail: str
    stderr_tail: str

    def to_dict(self) -> dict[str, object]:
        return {
            "command": self.command,
            "command_id": self.command_id,
            "cwd": self.cwd,
            "returncode": self.returncode,
            "stderr_tail": self.stderr_tail,
            "stdout_tail": self.stdout_tail,
        }


def _tail(text: str, limit: int = 2500) -> str:
    return text[-limit:]


def _run_command(command_id: str, command: list[str], cwd: Path) -> CommandResult:
    result = subprocess.run(
        command,
        cwd=str(cwd),
        text=True,
        capture_output=True,
        check=False,
    )
    command_result = CommandResult(
        command_id=command_id,
        command=command,
        cwd=str(cwd),
        returncode=result.returncode,
        stdout_tail=_tail(result.stdout),
        stderr_tail=_tail(result.stderr),
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"{command_id} failed with exit code {result.returncode}\n"
            f"STDOUT:\n{command_result.stdout_tail}\nSTDERR:\n{command_result.stderr_tail}"
        )
    return command_result


def _prepare_replay_root(replay_root: Path | None) -> Path:
    if replay_root is not None:
        if replay_root.exists():
            shutil.rmtree(replay_root)
        replay_root.mkdir(parents=True, exist_ok=True)
        return replay_root
    return Path(tempfile.mkdtemp(prefix="upi_factory_v1_clean_replay_"))


def execute_clean_checkout_replay(
    source_root: Path,
    checkout_ref: str,
    replay_root: Path | None,
) -> tuple[Path, tuple[CommandResult, ...]]:
    root = _prepare_replay_root(replay_root)
    checkout_dir = root / "upi_dispute_resolution_factory"

    commands: list[CommandResult] = []
    commands.append(
        _run_command(
            "git_clone_local_repository",
            ["git", "clone", "--no-hardlinks", str(source_root), str(checkout_dir)],
            root,
        )
    )
    commands.append(
        _run_command(
            "checkout_replay_capable_candidate_ref",
            ["git", "checkout", checkout_ref],
            checkout_dir,
        )
    )
    commands.append(
        _run_command(
            "verify_clean_checkout_status",
            ["git", "status", "--short"],
            checkout_dir,
        )
    )
    if commands[-1].stdout_tail.strip():
        raise RuntimeError("Clean checkout is not clean after tag checkout.")

    commands.append(
        _run_command(
            "verify_python_310_runtime",
            [sys.executable, "--version"],
            checkout_dir,
        )
    )
    if "Python 3.10." not in commands[-1].stdout_tail and "Python 3.10." not in commands[-1].stderr_tail:
        raise RuntimeError("Replay Python runtime is not Python 3.10.x.")

    commands.append(
        _run_command(
            "validate_phase14n_replay_gate",
            [sys.executable, "scripts/validate_phase14n_v1_release_candidate_replay_gate.py"],
            checkout_dir,
        )
    )
    commands.append(
        _run_command(
            "run_phase14n_targeted_tests",
            [sys.executable, "-m", "pytest", "tests/test_phase14n_v1_release_candidate_replay_gate.py"],
            checkout_dir,
        )
    )
    commands.append(
        _run_command(
            "run_generated_application_tests",
            [sys.executable, "-m", "pytest", *GENERATED_APP_TEST_PATHS],
            checkout_dir,
        )
    )
    commands.append(
        _run_command(
            "build_replay_gate_evidence_from_checkout",
            [sys.executable, "scripts/build_v1_release_candidate_replay_gate.py"],
            checkout_dir,
        )
    )

    return checkout_dir, tuple(commands)


def build_actual_clean_checkout_v1_replay_proof(
    source_root: Path,
    checkout_ref: str = DEFAULT_CHECKOUT_REF,
    execute_replay: bool = False,
    replay_root: Path | None = None,
    requirement_id: str = "upi_dispute_resolution.default_requirement",
) -> dict[str, object]:
    supporting_gate = build_v1_release_candidate_replay_gate(requirement_id=requirement_id)

    command_results: tuple[CommandResult, ...] = ()
    checkout_dir: Path | None = None
    if execute_replay:
        checkout_dir, command_results = execute_clean_checkout_replay(
            source_root=source_root.resolve(),
            checkout_ref=checkout_ref,
            replay_root=replay_root,
        )

    return {
        "actual_clean_checkout_performed": execute_replay,
        "allowlisted_subprocess_commands_only": True,
        "app_id": APP_ID,
        "arbitrary_shell_execution_performed": False,
        "auto_merge_performed": False,
        "auto_release_performed": False,
        "auto_tag_performed": False,
        "boundary_between_generated_application_and_certification": list(CERTIFICATION_BOUNDARY),
        "certification_ready_not_certified": True,
        "checkout_ref": checkout_ref,
        "clean_checkout_is_non_destructive": True,
        "command_results": [result.to_dict() for result in command_results],
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
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
        "real_generated_application_deleted": False,
        "real_generated_application_overwritten": False,
        "release_execution_performed": False,
        "replay_checkout_dir": str(checkout_dir) if checkout_dir is not None else "",
        "replay_steps": list(REPLAY_STEPS),
        "requirement_id": requirement_id,
        "schema_version": "actual-clean-checkout-v1-replay-proof.v1",
        "source_root": str(source_root.resolve()),
        "status": READY,
        "supporting_replay_gate_expected_status": PHASE14N_READY,
        "supporting_replay_gate_status": supporting_gate["status"],
        "what_sits_between_generated_application_and_certification": list(CERTIFICATION_BOUNDARY),
    }


def validate_actual_clean_checkout_v1_replay_proof(
    proof: dict[str, object],
    require_executed: bool = False,
) -> list[str]:
    failures: list[str] = []
    if proof.get("schema_version") != "actual-clean-checkout-v1-replay-proof.v1":
        failures.append("Invalid actual clean-checkout replay proof schema")
    if proof.get("app_id") != APP_ID:
        failures.append("Unexpected app_id")
    if proof.get("status") != READY:
        failures.append("Actual clean-checkout replay proof must be ready")

    for key in [
        "allowlisted_subprocess_commands_only",
        "clean_checkout_is_non_destructive",
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
        "real_generated_application_deleted",
        "real_generated_application_overwritten",
        "release_execution_performed",
    ]:
        if proof.get(key) is not False:
            failures.append(f"{key} must be false")

    if require_executed and proof.get("actual_clean_checkout_performed") is not True:
        failures.append("Actual clean-checkout replay must be executed")

    steps_value = proof.get("replay_steps")
    if not isinstance(steps_value, list):
        failures.append("Replay steps must be listed")
    else:
        step_names = {str(item) for item in steps_value}
        for step in REPLAY_STEPS:
            if step not in step_names:
                failures.append(f"Missing replay step: {step}")

    if require_executed:
        command_results = proof.get("command_results")
        if not isinstance(command_results, list) or not command_results:
            failures.append("Executed proof must include command results")
        else:
            command_ids: set[str] = set()
            for result in command_results:
                if isinstance(result, dict):
                    command_id = result.get("command_id")
                    if isinstance(command_id, str):
                        command_ids.add(command_id)
                    if result.get("returncode") != 0:
                        failures.append(f"Command failed in proof: {command_id}")
            required_commands = {
                "git_clone_local_repository",
                "checkout_replay_capable_candidate_ref",
                "verify_clean_checkout_status",
                "verify_python_310_runtime",
                "validate_phase14n_replay_gate",
                "run_phase14n_targeted_tests",
                "run_generated_application_tests",
                "build_replay_gate_evidence_from_checkout",
            }
            for command_id in required_commands:
                if command_id not in command_ids:
                    failures.append(f"Missing executed command: {command_id}")

    boundary_value = proof.get("what_sits_between_generated_application_and_certification")
    if not isinstance(boundary_value, list):
        failures.append("Certification boundary must be listed")
    else:
        boundary_names = {str(item) for item in boundary_value}
        for item in CERTIFICATION_BOUNDARY:
            if item not in boundary_names:
                failures.append(f"Missing certification boundary item: {item}")

    if proof.get("supporting_replay_gate_status") != PHASE14N_READY:
        failures.append("Supporting Phase 14N replay gate must be ready")
    return failures


def write_replay_proof(proof: dict[str, object], audit_out: Path) -> None:
    audit_out.parent.mkdir(parents=True, exist_ok=True)
    audit_out.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build actual clean-checkout v1 replay proof.")
    parser.add_argument("--source-root", type=Path, default=Path.cwd())
    parser.add_argument("--checkout-ref", default=DEFAULT_CHECKOUT_REF)
    parser.add_argument("--execute-replay", action="store_true")
    parser.add_argument("--replay-root", type=Path)
    parser.add_argument("--requirement-id", default="upi_dispute_resolution.default_requirement")
    parser.add_argument("--audit-out", type=Path)
    args = parser.parse_args()

    proof = build_actual_clean_checkout_v1_replay_proof(
        source_root=args.source_root,
        checkout_ref=args.checkout_ref,
        execute_replay=args.execute_replay,
        replay_root=args.replay_root,
        requirement_id=args.requirement_id,
    )
    if args.audit_out is not None:
        write_replay_proof(proof, args.audit_out)
    print(json.dumps(proof, indent=2, sort_keys=True))
    failures = validate_actual_clean_checkout_v1_replay_proof(
        proof,
        require_executed=args.execute_replay,
    )
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
