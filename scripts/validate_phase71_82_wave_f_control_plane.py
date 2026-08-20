#!/usr/bin/env python3
from __future__ import annotations

import atexit
import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

_STARTUP_PYCACHE = tempfile.TemporaryDirectory(
    prefix="phase71_82_wave_f_startup_pycache_"
)
sys.pycache_prefix = _STARTUP_PYCACHE.name
atexit.register(_STARTUP_PYCACHE.cleanup)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from factory.generators.mock_dispute_app_generator import generate  # noqa: E402


RUN_ID_A = "phase71_82_wave_f_control_plane_a"
RUN_ID_B = "phase71_82_wave_f_control_plane_b"
TEMPLATE_MANIFEST_PATH = (
    PROJECT_ROOT / "factory/templates/mock_dispute_app/template_manifest.v1.json"
)
EXPECTED_GENERATED_FILE_COUNT = len(
    json.loads(TEMPLATE_MANIFEST_PATH.read_text(encoding="utf-8"))["template_files"]
)
REQUIRED_WAVE_F_FILES = {
    "generated_application/app/control_plane/policy.py",
    "generated_application/app/tests/security/test_control_plane_policy.py",
    "generated_application/evidence/assurance/control_plane_governance.json",
}


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON root must be an object: {path}")
    return value


def generated_file_fingerprints(manifest_path: Path) -> dict[str, tuple[str, int]]:
    manifest = read_json(manifest_path)
    files = manifest.get("generated_files", [])
    if not isinstance(files, list):
        raise RuntimeError("generated_files must be a list")
    return {
        str(item["relative_path"]): (str(item["sha256"]), int(item["size_bytes"]))
        for item in files
        if isinstance(item, dict)
    }


def validate_generated_control_plane(generated_root: Path) -> list[str]:
    sys.path.insert(0, str(generated_root))
    try:
        from generated_application.app.control_plane.policy import (
            Action,
            AgentContract,
            ApprovalGrant,
            ControlPlanePolicyEngine,
            Decision,
            PolicyRequest,
        )

        agent = AgentContract(
            agent_id="independent-local-verifier",
            allowed_actions=frozenset(
                {
                    Action.READ_EVIDENCE,
                    Action.RUN_LOCAL_TESTS,
                    Action.START_LOCAL_RUNTIME,
                    Action.RECOMMEND_PORTFOLIO,
                }
            ),
            max_iterations=4,
            independent_verification_required=True,
        )
        request = PolicyRequest(
            action=Action.START_LOCAL_RUNTIME,
            application_id="upi_dispute_resolution",
            version_id="v1",
            process_id="runtime_001",
            port=18042,
            state_root="state/runtime_001",
            evidence_root="evidence/runtime_001",
            approval_nonce="nonce-001",
        )
        now = datetime(2026, 7, 26, tzinfo=timezone.utc)
        grant = ApprovalGrant(
            scope="runtime_001",
            action=Action.START_LOCAL_RUNTIME,
            nonce="nonce-001",
            approved_at_utc=now.isoformat().replace("+00:00", "Z"),
            expires_at_utc=(now + timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
        )
        engine = ControlPlanePolicyEngine()
        checks = []

        allowed = engine.decide(request, agent=agent, approvals=[grant], now_utc=now)
        if allowed.decision != Decision.ALLOW:
            raise RuntimeError("valid scoped approval was not allowed")
        if allowed.consumed_approval_nonce != "nonce-001":
            raise RuntimeError("allowed approval did not expose consumed nonce contract")
        checks.append("scoped_unexpired_approval_allows_local_runtime")

        replay_same_grant = engine.decide(request, agent=agent, approvals=[grant], now_utc=now)
        if replay_same_grant.decision != Decision.DENY:
            raise RuntimeError("same approval grant was reusable through one policy engine")
        checks.append("policy_engine_consumes_and_rejects_same_nonce_replay")

        expired = ApprovalGrant(
            scope="runtime_001",
            action=Action.START_LOCAL_RUNTIME,
            nonce="nonce-001",
            approved_at_utc=now.isoformat().replace("+00:00", "Z"),
            expires_at_utc=(now - timedelta(seconds=1)).isoformat().replace("+00:00", "Z"),
        )
        if engine.decide(request, agent=agent, approvals=[expired], now_utc=now).decision != Decision.DENY:
            raise RuntimeError("expired approval did not fail closed")
        checks.append("expired_approval_denied")

        malformed = ApprovalGrant(
            scope="runtime_001",
            action=Action.START_LOCAL_RUNTIME,
            nonce="nonce-001",
            approved_at_utc=now.isoformat().replace("+00:00", "Z"),
            expires_at_utc="not-a-date",
        )
        if engine.decide(request, agent=agent, approvals=[malformed], now_utc=now).decision != Decision.DENY:
            raise RuntimeError("malformed approval expiry did not fail closed")
        checks.append("malformed_approval_expiry_denied")

        replayed = ApprovalGrant(
            scope="runtime_001",
            action=Action.START_LOCAL_RUNTIME,
            nonce="nonce-001",
            approved_at_utc=now.isoformat().replace("+00:00", "Z"),
            expires_at_utc=(now + timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
            consumed=True,
        )
        if engine.decide(request, agent=agent, approvals=[replayed], now_utc=now).decision != Decision.DENY:
            raise RuntimeError("replayed approval did not fail closed")
        checks.append("replayed_approval_denied")

        for action in (Action.MERGE, Action.PUSH, Action.RELEASE, Action.DEPLOY, Action.CERTIFY, Action.DESTROY):
            if engine.decide(PolicyRequest(**{**request.__dict__, "action": action}), agent=agent).decision != Decision.DENY:
                raise RuntimeError(f"human-gated action was not denied: {action.value}")
        checks.append("explicit_human_gates_denied")

        for action in (Action.MODIFY_PROMPTS, Action.MODIFY_MODELS, Action.MODIFY_POLICIES, Action.MODIFY_TESTS):
            if engine.decide(PolicyRequest(**{**request.__dict__, "action": action}), agent=agent).decision != Decision.DENY:
                raise RuntimeError(f"self-modification action was not denied: {action.value}")
        checks.append("silent_self_modification_denied")

        isolated = PolicyRequest(**{**request.__dict__, "action": Action.READ_EVIDENCE, "state_root": "same", "evidence_root": "same"})
        if engine.decide(isolated, agent=agent).decision != Decision.DENY:
            raise RuntimeError("state/evidence root collision did not fail closed")
        checks.append("state_evidence_root_collision_denied")

        recommendation = engine.decide(
            PolicyRequest(**{**request.__dict__, "action": Action.RECOMMEND_PORTFOLIO, "approval_nonce": None}),
            agent=agent,
        )
        if recommendation.decision != Decision.ALLOW or recommendation.recommendation_only is not True:
            raise RuntimeError("portfolio assessment must be recommendation-only")
        checks.append("portfolio_assessment_recommendation_only")

        evidence = read_json(
            generated_root / "generated_application/evidence/assurance/control_plane_governance.json"
        )
        if evidence.get("portfolio_assessment", {}).get("mode") != "recommendation_only":
            raise RuntimeError("control-plane evidence must be recommendation-only")
        if evidence.get("approval_controls", {}).get("expiry_required") is not True:
            raise RuntimeError("control-plane evidence must require approval expiry")
        if evidence.get("approval_controls", {}).get("policy_engine_consumes_nonce") is not True:
            raise RuntimeError("control-plane evidence must record engine nonce consumption")
        checks.append("control_plane_evidence_shape")
        return checks
    finally:
        try:
            sys.path.remove(str(generated_root))
        except ValueError:
            pass


def validate() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="phase71_82_wave_f_generation_") as workspace:
        workspace_root = Path(workspace)
        first = generate(run_id=RUN_ID_A, workspace_root=workspace_root, clean=True)
        second = generate(run_id=RUN_ID_B, workspace_root=workspace_root, clean=True)

        emitted_files = {item.relative_path for item in first.generated_files}
        missing = sorted(REQUIRED_WAVE_F_FILES - emitted_files)
        if missing:
            raise RuntimeError(f"Fresh generated output missing Wave F files: {missing}")
        if len(first.generated_files) != EXPECTED_GENERATED_FILE_COUNT:
            raise RuntimeError(
                f"Expected {EXPECTED_GENERATED_FILE_COUNT} generated files, got {len(first.generated_files)}"
            )

        first_fingerprints = generated_file_fingerprints(first.manifest_path)
        second_fingerprints = generated_file_fingerprints(second.manifest_path)
        if first_fingerprints != second_fingerprints:
            raise RuntimeError("Two-build generated file comparison failed")

        manifest = read_json(first.manifest_path)
        control_plane = manifest.get("control_plane_policy", {})
        if not isinstance(control_plane, dict) or control_plane.get("deterministic_fail_closed") is not True:
            raise RuntimeError("generation manifest missing fail-closed control-plane policy")
        if control_plane.get("portfolio_assessment_mode") != "recommendation_only":
            raise RuntimeError("portfolio assessment must remain recommendation-only")

        return {
            "passed": True,
            "run_ids": [first.run_id, second.run_id],
            "generated_file_count": len(first.generated_files),
            "wave_f_generated_files": sorted(REQUIRED_WAVE_F_FILES),
            "structural_checks": validate_generated_control_plane(first.output_dir / "generated"),
            "two_build_comparison": {
                "status": "passed",
                "compared_generated_template_files": len(first_fingerprints),
            },
            "control_plane_policy": control_plane,
            "live_provider_calls_allowed": manifest["live_provider_calls_allowed"],
            "real_payment_calls_allowed": manifest["real_payment_calls_allowed"],
            "official_certification_claimed": manifest["official_certification_claimed"],
        }


def main() -> int:
    try:
        print(json.dumps(validate(), indent=2) + "\n")
    except Exception as exc:
        print(json.dumps({"passed": False, "error": str(exc)}, indent=2) + "\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
