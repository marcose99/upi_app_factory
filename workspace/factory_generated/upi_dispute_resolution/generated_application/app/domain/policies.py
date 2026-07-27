from __future__ import annotations

from .entities import Dispute, DisputeState


def initial_policy_state(dispute: Dispute) -> DisputeState:
    if "fraud" in dispute.reason.lower():
        return DisputeState.REJECTED
    return DisputeState.VALIDATED
