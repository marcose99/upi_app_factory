from __future__ import annotations

from datetime import datetime, timedelta, timezone
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from generated_application.app.control_plane.policy import (
    Action,
    AgentContract,
    ApprovalGrant,
    ControlPlanePolicyEngine,
    Decision,
    PolicyRequest,
)


def _agent() -> AgentContract:
    return AgentContract(
        agent_id="local-verifier",
        allowed_actions=frozenset(
            {Action.READ_EVIDENCE, Action.RUN_LOCAL_TESTS, Action.START_LOCAL_RUNTIME, Action.RECOMMEND_PORTFOLIO}
        ),
        max_iterations=4,
        independent_verification_required=True,
    )


def _request(action: Action, *, nonce: str | None = None) -> PolicyRequest:
    return PolicyRequest(
        action=action,
        application_id="upi_dispute_resolution",
        version_id="v1",
        process_id="runtime_001",
        port=18042,
        state_root="state/runtime_001",
        evidence_root="evidence/runtime_001",
        approval_nonce=nonce,
    )


def test_policy_fails_closed_for_human_gates_and_self_modification() -> None:
    engine = ControlPlanePolicyEngine()

    merge = engine.decide(_request(Action.MERGE), agent=_agent())
    prompt_change = engine.decide(_request(Action.MODIFY_PROMPTS), agent=_agent())

    assert merge.decision == Decision.DENY
    assert merge.human_gate_required is True
    assert prompt_change.decision == Decision.DENY
    assert "self-modification prohibited" in prompt_change.reason


def test_start_runtime_requires_scoped_unexpired_nonce_and_rejects_replay() -> None:
    now = datetime(2026, 7, 26, tzinfo=timezone.utc)
    grant = ApprovalGrant(
        scope="runtime_001",
        action=Action.START_LOCAL_RUNTIME,
        nonce="nonce-001",
        approved_at_utc=now.isoformat().replace("+00:00", "Z"),
        expires_at_utc=(now + timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
    )
    engine = ControlPlanePolicyEngine()

    allowed = engine.decide(_request(Action.START_LOCAL_RUNTIME, nonce="nonce-001"), agent=_agent(), approvals=[grant], now_utc=now)
    replayed_same_grant = engine.decide(
        _request(Action.START_LOCAL_RUNTIME, nonce="nonce-001"),
        agent=_agent(),
        approvals=[grant],
        now_utc=now,
    )
    replayed = engine.decide(
        _request(Action.START_LOCAL_RUNTIME, nonce="nonce-001"),
        agent=_agent(),
        approvals=[ApprovalGrant(**{**grant.__dict__, "consumed": True})],
        now_utc=now,
    )
    expired = engine.decide(
        _request(Action.START_LOCAL_RUNTIME, nonce="nonce-001"),
        agent=_agent(),
        approvals=[ApprovalGrant(**{**grant.__dict__, "expires_at_utc": (now - timedelta(seconds=1)).isoformat().replace("+00:00", "Z")})],
        now_utc=now,
    )

    assert allowed.decision == Decision.ALLOW
    assert allowed.consumed_approval_nonce == "nonce-001"
    assert replayed_same_grant.decision == Decision.DENY
    assert replayed.decision == Decision.DENY
    assert expired.decision == Decision.DENY


def test_multi_application_state_and_evidence_are_isolated() -> None:
    engine = ControlPlanePolicyEngine()

    denied = engine.decide(
        PolicyRequest(
            action=Action.READ_EVIDENCE,
            application_id="upi_dispute_resolution",
            version_id="v1",
            process_id="runtime_002",
            port=18043,
            state_root="shared/root",
            evidence_root="shared/root",
        ),
        agent=_agent(),
    )
    recommendation = engine.decide(_request(Action.RECOMMEND_PORTFOLIO), agent=_agent())

    assert denied.decision == Decision.DENY
    assert "isolated" in denied.reason
    assert recommendation.decision == Decision.ALLOW
    assert recommendation.recommendation_only is True
