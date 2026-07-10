from __future__ import annotations

import pytest

from tools.lifecycle_orchestrator.models import (
    ApprovalSet,
    LifecycleState,
    STATE_ORDER,
)


def test_approval_set_accepts_one_time_run_approval() -> None:
    approvals = ApprovalSet.from_csv("commit,merge,push")
    assert approvals.commit is True
    assert approvals.merge is True
    assert approvals.push is True
    assert approvals.tag is False
    assert approvals.release is False


def test_approval_set_rejects_unknown_action() -> None:
    with pytest.raises(ValueError, match="Unknown approval"):
        ApprovalSet.from_csv("commit,deploy")


def test_approval_lookup_rejects_unknown_action() -> None:
    with pytest.raises(ValueError, match="Unknown protected action"):
        ApprovalSet().approved("deploy")


def test_lifecycle_state_order_ends_in_closed() -> None:
    assert STATE_ORDER[0] is LifecycleState.CREATED
    assert STATE_ORDER[-1] is LifecycleState.CLOSED
    assert LifecycleState.PUSHED in STATE_ORDER
