from __future__ import annotations

from app.feedback.models import FeedbackSeverity, FeedbackStatus, HumanFeedback

_FEEDBACK_STORE: dict[str, HumanFeedback] = {}


def save_feedback(feedback: HumanFeedback) -> HumanFeedback:
    _FEEDBACK_STORE[feedback.feedback_id] = feedback
    return feedback


def get_feedback(feedback_id: str) -> HumanFeedback | None:
    return _FEEDBACK_STORE.get(feedback_id)


def list_feedback() -> list[HumanFeedback]:
    return list(_FEEDBACK_STORE.values())


def open_blockers() -> list[HumanFeedback]:
    closed_statuses = {FeedbackStatus.CLOSED, FeedbackStatus.RESOLVED, FeedbackStatus.VALIDATED}
    return [
        item
        for item in _FEEDBACK_STORE.values()
        if item.severity == FeedbackSeverity.BLOCKER and item.status not in closed_statuses
    ]
