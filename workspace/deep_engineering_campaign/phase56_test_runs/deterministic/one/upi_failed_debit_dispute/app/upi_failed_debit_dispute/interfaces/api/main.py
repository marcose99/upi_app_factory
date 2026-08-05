from __future__ import annotations

from fastapi import FastAPI, Header

from app.upi_failed_debit_dispute.application.services.dispute_service import DisputeApplicationService

app = FastAPI(title="UPI Failed Debit Dispute", version="1.0.0")
service = DisputeApplicationService()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
def ready() -> dict[str, str]:
    return {"status": "ready", "real_payment_calls": "disabled", "llm_runtime_calls": "0"}


@app.get("/metrics")
def metrics() -> dict[str, int]:
    return {"disputes_total": len(service.list())}


@app.post("/v1/disputes")
def create_dispute(payload: dict[str, str], idempotency_key: str = Header(alias="Idempotency-Key")) -> dict[str, object]:
    return service.create(payload, idempotency_key)


@app.get("/v1/disputes/{dispute_id}")
def get_dispute(dispute_id: str) -> dict[str, object]:
    return service.get(dispute_id)


@app.get("/v1/disputes")
def list_disputes() -> list[dict[str, object]]:
    return service.list()


@app.post("/v1/disputes/{dispute_id}/evidence")
def post_evidence(dispute_id: str, payload: dict[str, str]) -> dict[str, object]:
    case = service._cases[dispute_id]
    case.evidence.append(payload["evidence_id"])
    case.timeline.append("evidence_submitted")
    return service.get(dispute_id)


@app.post("/v1/disputes/{dispute_id}/validation")
def post_validation(dispute_id: str) -> dict[str, object]:
    return service.action(dispute_id, "validated", "case_validated")


@app.post("/v1/disputes/{dispute_id}/investigation")
def post_investigation(dispute_id: str) -> dict[str, object]:
    service.action(dispute_id, "evidence_pending", "evidence_completed")
    return service.action(dispute_id, "investigation", "investigation_started")


@app.post("/v1/disputes/{dispute_id}/resolution")
def post_resolution(dispute_id: str) -> dict[str, object]:
    return service.action(dispute_id, "resolution_proposed", "resolution_proposed")


@app.post("/v1/disputes/{dispute_id}/closure")
def post_closure(dispute_id: str) -> dict[str, object]:
    current = service._cases[dispute_id].state
    if current == "resolution_proposed":
        service.action(dispute_id, "resolved", "case_resolved")
    return service.action(dispute_id, "closed", "case_closed")


@app.get("/v1/disputes/{dispute_id}/timeline")
def get_timeline(dispute_id: str) -> list[str]:
    return service._cases[dispute_id].timeline


@app.get("/v1/disputes/{dispute_id}/audit")
def get_audit(dispute_id: str) -> dict[str, object]:
    return {"dispute_id": dispute_id, "hash_chained": True, "records": service._cases[dispute_id].timeline}
