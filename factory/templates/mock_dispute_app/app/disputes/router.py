from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.disputes.models import (
    CaseActionRequest,
    CreateCaseRequest,
    DisputeCase,
    FailedTransactionEvent,
)
from app.disputes.service import dispute_case_service

router = APIRouter(prefix="/disputes", tags=["mock-disputes"])


@router.get(
    "/mock-failed-transactions",
    response_model=list[FailedTransactionEvent],
)
def list_mock_failed_transactions() -> list[FailedTransactionEvent]:
    return dispute_case_service.list_failed_transactions()


@router.post(
    "/cases/from-failed-transaction",
    response_model=DisputeCase,
    status_code=status.HTTP_201_CREATED,
)
def create_case_from_failed_transaction(
    request: CreateCaseRequest,
) -> DisputeCase:
    try:
        return dispute_case_service.create_case(request)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"mock failed transaction not found: {request.transaction_id}",
        ) from exc


@router.get("/cases", response_model=list[DisputeCase])
def list_dispute_cases() -> list[DisputeCase]:
    return dispute_case_service.list_cases()


@router.get("/cases/{case_id}", response_model=DisputeCase)
def get_dispute_case(case_id: str) -> DisputeCase:
    try:
        return dispute_case_service.get_case(case_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"mock dispute case not found: {case_id}",
        ) from exc


@router.post("/cases/{case_id}/actions", response_model=DisputeCase)
def apply_dispute_case_action(
    case_id: str,
    request: CaseActionRequest,
) -> DisputeCase:
    try:
        return dispute_case_service.apply_action(case_id, request)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"mock dispute case not found: {case_id}",
        ) from exc
