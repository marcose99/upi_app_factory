from __future__ import annotations

import hashlib
from pathlib import PurePosixPath

from .contracts import EvidenceUploadRequest, EvidenceValidationResult

_ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".txt", ".json"}
_CUSTOMER_EVIDENCE_TYPES = {"customer_statement", "merchant_receipt", "upi_reference"}


def _stable_reference(*parts: str) -> str:
    joined = "|".join(parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16].upper()


def _file_extension(filename: str) -> str:
    return PurePosixPath(filename).suffix.lower()


def validate_evidence_upload(
    request: EvidenceUploadRequest,
) -> EvidenceValidationResult:
    """Validate local evidence metadata without touching external systems."""

    risk_flags: list[str] = []
    extension = _file_extension(request.filename)
    if extension not in _ALLOWED_EXTENSIONS:
        risk_flags.append("UNSUPPORTED_FILE_EXTENSION")
    if request.uploaded_by == "customer" and request.evidence_type not in _CUSTOMER_EVIDENCE_TYPES:
        risk_flags.append("CUSTOMER_UPLOADED_NON_CUSTOMER_EVIDENCE_TYPE")
    if request.content_size_bytes < 128:
        risk_flags.append("SUSPICIOUSLY_SMALL_EVIDENCE_FILE")

    accepted = len(risk_flags) == 0
    reference = _stable_reference(
        request.dispute_case_id,
        request.transaction_id,
        request.filename,
        request.content_sha256,
    )
    return EvidenceValidationResult(
        accepted=accepted,
        validation_status="ACCEPTED" if accepted else "REJECTED",
        evidence_id=f"EVD-{reference}",
        dispute_case_id=request.dispute_case_id,
        transaction_id=request.transaction_id,
        risk_flags=risk_flags,
        audit_event_type="evidence_upload_validated",
        audit_reference=f"AUD-{reference}",
    )
