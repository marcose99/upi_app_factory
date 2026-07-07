"""Generated evidence-validation capability."""
from __future__ import annotations

from .contracts import EvidenceUpload, EvidenceValidationResult

SUPPORTED_EXTENSIONS = (".pdf", ".png", ".jpg", ".jpeg")
MAX_EVIDENCE_SIZE_BYTES = 5_000_000


def validate_evidence(upload: EvidenceUpload) -> EvidenceValidationResult:
    issues: list[str] = []
    if not upload.case_id.strip():
        issues.append("missing_case_id")
    if not upload.filename.lower().endswith(SUPPORTED_EXTENSIONS):
        issues.append("unsupported_file_type")
    if not upload.content_hash.strip() or len(upload.content_hash.strip()) < 16:
        issues.append("weak_or_missing_content_hash")
    if upload.size_bytes <= 0:
        issues.append("empty_evidence_payload")
    if upload.size_bytes > MAX_EVIDENCE_SIZE_BYTES:
        issues.append("evidence_payload_too_large")
    return EvidenceValidationResult(
        case_id=upload.case_id,
        accepted=not issues,
        issues=tuple(issues),
    )
