from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from tools.factory_control_plane.common import (
    ControlPlaneError,
    canonical_json,
    load_json_object,
    sha256_bytes,
)
from tools.factory_control_plane.manifest import ORDERED_RISK, Risk

Outcome = Literal["allow", "pause", "deny"]


@dataclass(frozen=True)
class PolicyDecision:
    decision_id: str
    action: str
    risk: str
    outcome: Outcome
    human_required: bool
    policy_digest: str
    reasons: tuple[str, ...]

    def to_record(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "action": self.action,
            "risk": self.risk,
            "outcome": self.outcome,
            "human_required": self.human_required,
            "policy_digest": self.policy_digest,
            "reasons": list(self.reasons),
        }


class StandingPolicy:
    def __init__(self, path: Path) -> None:
        self.path = path.resolve()
        self.raw = load_json_object(self.path)
        self.digest = sha256_bytes(canonical_json(self.raw))
        self.auto_actions = set(_string_list(self.raw.get("automatic_actions")))
        self.human_actions = set(_string_list(self.raw.get("human_required_actions")))
        self.prohibited_actions = set(_string_list(self.raw.get("prohibited_actions")))
        self.max_auto_risk = str(self.raw.get("max_automatic_risk", "MODERATE"))
        conflicts = (
            (self.auto_actions & self.human_actions)
            | (self.auto_actions & self.prohibited_actions)
            | (self.human_actions & self.prohibited_actions)
        )
        if conflicts:
            raise ControlPlaneError(
                f"standing policy memberships must be disjoint: {sorted(conflicts)}"
            )
        if self.max_auto_risk not in ORDERED_RISK:
            raise ControlPlaneError("max_automatic_risk is invalid")

    def evaluate(self, action: str, risk: Risk | str) -> PolicyDecision:
        reasons: list[str] = [f"policy_digest={self.digest}"]
        outcome: Outcome = "deny"
        human = False
        if action in self.prohibited_actions:
            reasons.append("action is prohibited")
        elif action in self.human_actions:
            outcome = "pause"
            human = True
            reasons.append("human approval is mandatory for this action")
        elif (
            action in self.auto_actions
            and ORDERED_RISK.get(str(risk), 99) <= ORDERED_RISK[self.max_auto_risk]
        ):
            outcome = "allow"
            reasons.append("action and risk are within automatic standing policy")
        else:
            reasons.append("default deny for unknown or excessive risk")
        seed = {
            "action": action,
            "risk": str(risk),
            "policy_digest": self.digest,
            "outcome": outcome,
        }
        return PolicyDecision(
            decision_id=sha256_bytes(canonical_json(seed)),
            action=action,
            risk=str(risk),
            outcome=outcome,
            human_required=human,
            policy_digest=self.digest,
            reasons=tuple(reasons),
        )


def _string_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str))
