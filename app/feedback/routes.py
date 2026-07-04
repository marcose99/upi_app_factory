from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.feedback.models import FeedbackStatus, HumanFeedback, HumanFeedbackCreate, new_feedback_id, utc_now
from app.feedback.repository import get_feedback, list_feedback, open_blockers, save_feedback
from app.observability.audit import write_audit_event

router = APIRouter(prefix="/feedback", tags=["human-feedback"])


@router.post("", response_model=HumanFeedback)
def create_feedback(payload: HumanFeedbackCreate) -> HumanFeedback:
    audit_event_id = write_audit_event(
        action="feedback_submitted",
        target=payload.artifact_path or "unknown_artifact",
        result="SUBMITTED",
        details={"severity": payload.severity.value},
    )
    feedback = HumanFeedback(
        feedback_id=new_feedback_id(),
        created_at_utc=utc_now(),
        status=FeedbackStatus.SUBMITTED,
        title=payload.title,
        description=payload.description,
        reviewer_role=payload.reviewer_role,
        artifact_path=payload.artifact_path,
        agent_id=payload.agent_id,
        severity=payload.severity,
        quality_dimensions=payload.quality_dimensions,
        audit_event_ids=[audit_event_id],
    )
    return save_feedback(feedback)


@router.get("/reports/open-blockers")
def read_open_blockers() -> dict[str, object]:
    blockers = open_blockers()
    return {"open_blocker_count": len(blockers), "feedback_ids": [b.feedback_id for b in blockers]}


@router.get("/{feedback_id}", response_model=HumanFeedback)
def read_feedback(feedback_id: str) -> HumanFeedback:
    feedback = get_feedback(feedback_id)
    if feedback is None:
        raise HTTPException(status_code=404, detail="feedback_not_found")
    return feedback


@router.get("", response_model=list[HumanFeedback])
def read_all_feedback() -> list[HumanFeedback]:
    return list_feedback()
