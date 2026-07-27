from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import re
from typing import Any, Iterable


class Decision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"


class Action(str, Enum):
    READ_EVIDENCE = "read_evidence"
    RUN_LOCAL_TESTS = "run_local_tests"
    START_LOCAL_RUNTIME = "start_local_runtime"
    RECOMMEND_PORTFOLIO = "recommend_portfolio"
    MERGE = "merge"
    PUSH = "push"
    RELEASE = "release"
    DEPLOY = "deploy"
    CERTIFY = "certify"
    DESTROY = "destroy"
    MODIFY_PROMPTS = "modify_prompts"
    MODIFY_MODELS = "modify_models"
    MODIFY_POLICIES = "modify_policies"
    MODIFY_TESTS = "modify_tests"


HUMAN_GATE_ACTIONS = frozenset(
    {
        Action.MERGE,
        Action.PUSH,
        Action.RELEASE,
        Action.DEPLOY,
        Action.CERTIFY,
        Action.DESTROY,
    }
)
SELF_MODIFICATION_ACTIONS = frozenset(
    {
        Action.MODIFY_PROMPTS,
        Action.MODIFY_MODELS,
        Action.MODIFY_POLICIES,
        Action.MODIFY_TESTS,
    }
)
LOCAL_ACTIONS = frozenset(
    {
        Action.READ_EVIDENCE,
        Action.RUN_LOCAL_TESTS,
        Action.START_LOCAL_RUNTIME,
        Action.RECOMMEND_PORTFOLIO,
    }
)
APP_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{2,63}$")
RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{2,96}$")


@dataclass(frozen=True)
class ApprovalGrant:
    scope: str
    action: Action
    nonce: str
    approved_at_utc: str
    expires_at_utc: str
    consumed: bool = False

    def validate_for(self, *, scope: str, action: Action, nonce: str, now_utc: datetime) -> None:
        if self.scope != scope or self.action != action or self.nonce != nonce:
            raise PermissionError("approval scope rejected")
        if self.consumed:
            raise PermissionError("approval replay rejected")
        try:
            expires_at = datetime.fromisoformat(self.expires_at_utc.replace("Z", "+00:00"))
        except ValueError as exc:
            raise PermissionError("approval expiry invalid") from exc
        if expires_at <= now_utc:
            raise PermissionError("approval expired")


@dataclass(frozen=True)
class AgentContract:
    agent_id: str
    allowed_actions: frozenset[Action]
    max_iterations: int
    independent_verification_required: bool

    def validate(self) -> None:
        if self.max_iterations < 1 or self.max_iterations > 8:
            raise ValueError("agent loop bound is outside governed range")
        if not self.allowed_actions.issubset(LOCAL_ACTIONS):
            raise ValueError("agent contract exceeds least-privilege local actions")
        if not self.independent_verification_required:
            raise ValueError("independent verification is required")


@dataclass(frozen=True)
class IsolationBinding:
    application_id: str
    version_id: str
    process_id: str
    port: int
    state_root: str
    evidence_root: str

    def validate(self) -> None:
        if not APP_ID_PATTERN.fullmatch(self.application_id):
            raise ValueError("application id is not governed")
        if not RUN_ID_PATTERN.fullmatch(self.process_id):
            raise ValueError("process id is not governed")
        if self.port < 1024 or self.port > 65535:
            raise ValueError("port is outside governed local range")
        if self.state_root == self.evidence_root:
            raise ValueError("state and evidence roots must be isolated")
        for value in (self.state_root, self.evidence_root):
            if value.startswith("/") or ".." in value.split("/"):
                raise ValueError("isolation roots must be relative child paths")


@dataclass(frozen=True)
class PolicyRequest:
    action: Action
    application_id: str
    version_id: str
    process_id: str
    port: int
    state_root: str
    evidence_root: str
    approval_nonce: str | None = None
    recommendation_only: bool = True


@dataclass(frozen=True)
class PolicyDecision:
    decision: Decision
    reason: str
    human_gate_required: bool
    recommendation_only: bool
    decision_sha256: str
    consumed_approval_nonce: str | None = None

    @classmethod
    def build(
        cls,
        *,
        decision: Decision,
        reason: str,
        human_gate_required: bool,
        recommendation_only: bool,
        material: dict[str, Any],
        consumed_approval_nonce: str | None = None,
    ) -> "PolicyDecision":
        digest = hashlib.sha256(
            json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return cls(
            decision,
            reason,
            human_gate_required,
            recommendation_only,
            digest,
            consumed_approval_nonce,
        )


class ControlPlanePolicyEngine:
    def __init__(self) -> None:
        self._consumed_approval_keys: set[tuple[str, Action, str]] = set()

    def decide(
        self,
        request: PolicyRequest,
        *,
        agent: AgentContract,
        approvals: Iterable[ApprovalGrant] = (),
        now_utc: datetime | None = None,
    ) -> PolicyDecision:
        now = now_utc or datetime.now(timezone.utc)
        material = {
            "action": request.action.value,
            "application_id": request.application_id,
            "version_id": request.version_id,
            "process_id": request.process_id,
            "port": request.port,
        }
        consumed_approval_nonce: str | None = None
        try:
            agent.validate()
            IsolationBinding(
                application_id=request.application_id,
                version_id=request.version_id,
                process_id=request.process_id,
                port=request.port,
                state_root=request.state_root,
                evidence_root=request.evidence_root,
            ).validate()
        except ValueError as exc:
            return PolicyDecision.build(
                decision=Decision.DENY,
                reason=str(exc),
                human_gate_required=True,
                recommendation_only=True,
                material=material,
            )

        if request.action in SELF_MODIFICATION_ACTIONS:
            return PolicyDecision.build(
                decision=Decision.DENY,
                reason="silent prompt/model/policy/test self-modification prohibited",
                human_gate_required=True,
                recommendation_only=True,
                material=material,
            )
        if request.action in HUMAN_GATE_ACTIONS:
            return PolicyDecision.build(
                decision=Decision.DENY,
                reason="explicit human gate required outside generated app authority",
                human_gate_required=True,
                recommendation_only=True,
                material=material,
            )
        if request.action not in agent.allowed_actions:
            return PolicyDecision.build(
                decision=Decision.DENY,
                reason="agent action outside least-privilege contract",
                human_gate_required=False,
                recommendation_only=True,
                material=material,
            )
        if request.action == Action.START_LOCAL_RUNTIME:
            if not request.approval_nonce:
                return PolicyDecision.build(
                    decision=Decision.DENY,
                    reason="scoped approval nonce required",
                    human_gate_required=True,
                    recommendation_only=True,
                    material=material,
                )
            matched_approval: ApprovalGrant | None = None
            for approval in approvals:
                try:
                    approval.validate_for(
                        scope=request.process_id,
                        action=request.action,
                        nonce=request.approval_nonce,
                        now_utc=now,
                    )
                    replay_key = (approval.scope, approval.action, approval.nonce)
                    if replay_key in self._consumed_approval_keys:
                        raise PermissionError("approval replay rejected")
                    matched_approval = approval
                    break
                except PermissionError:
                    continue
            else:
                return PolicyDecision.build(
                    decision=Decision.DENY,
                    reason="approval missing, expired or replayed",
                    human_gate_required=True,
                    recommendation_only=True,
                    material=material,
                )
            if matched_approval is not None:
                replay_key = (
                    matched_approval.scope,
                    matched_approval.action,
                    matched_approval.nonce,
                )
                self._consumed_approval_keys.add(replay_key)
                consumed_approval_nonce = matched_approval.nonce
        return PolicyDecision.build(
            decision=Decision.ALLOW,
            reason="local deterministic action allowed",
            human_gate_required=False,
            recommendation_only=request.action == Action.RECOMMEND_PORTFOLIO,
            material=material,
            consumed_approval_nonce=consumed_approval_nonce,
        )
