from __future__ import annotations

from enum import Enum

from tools.factory_control_plane.common import ControlPlaneError


class LifecycleState(str, Enum):
    NEW = "NEW"
    INTAKE_VALIDATED = "INTAKE_VALIDATED"
    RISK_CLASSIFIED = "RISK_CLASSIFIED"
    PLAN_APPROVED_BY_POLICY = "PLAN_APPROVED_BY_POLICY"
    WORKSPACE_READY = "WORKSPACE_READY"
    ENGINEERING = "ENGINEERING"
    OFFLINE_VALIDATED = "OFFLINE_VALIDATED"
    OPTIONAL_LIVE_EVALUATED = "OPTIONAL_LIVE_EVALUATED"
    CANDIDATE_SEALED = "CANDIDATE_SEALED"
    PR_OPEN = "PR_OPEN"
    HOSTED_CHECKS_PASSED = "HOSTED_CHECKS_PASSED"
    MERGED = "MERGED"
    POSTMERGE_ACCEPTED = "POSTMERGE_ACCEPTED"
    HANDOFF_BUILT = "HANDOFF_BUILT"
    CLEANED = "CLEANED"
    CLOSED = "CLOSED"


STATE_ORDER: tuple[LifecycleState, ...] = tuple(LifecycleState)
STATE_INDEX = {state: index for index, state in enumerate(STATE_ORDER)}


def advance(current: LifecycleState, target: LifecycleState) -> LifecycleState:
    if current is LifecycleState.CLOSED and target is not LifecycleState.CLOSED:
        raise ControlPlaneError("CLOSED is terminal")
    if STATE_INDEX[target] < STATE_INDEX[current]:
        raise ControlPlaneError(
            f"backward transition is forbidden: {current.value}->{target.value}"
        )
    return target
