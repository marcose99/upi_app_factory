from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
from typing import Any, cast

from pydantic import ValidationError

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
GENERATED_ROOT = (
    PROJECT_ROOT
    / "workspace"
    / "factory_generated"
    / "upi_dispute_resolution"
    / "generated_application"
    / "phase13s_evidence_upload_validation"
)
ARTIFACT_DIR = (
    PROJECT_ROOT
    / "workspace"
    / "factory_generated"
    / "upi_dispute_resolution"
    / "lifecycle_artifacts"
    / "phase13s"
)


def run_phase13s_generation() -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONPATH"] = ":".join(
        [
            str(PROJECT_ROOT / "src"),
            str(PROJECT_ROOT / "scripts"),
            str(PROJECT_ROOT),
            env.get("PYTHONPATH", ""),
        ]
    )
    result = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "run_phase13s_agent_owned_application_generation.py"),
        ],
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    return cast(dict[str, Any], json.loads(result.stdout))


def test_phase13s_agent_owned_generation_outputs_and_behavior() -> None:
    output = run_phase13s_generation()
    assert output["passed"] is True
    assert output["phase"] == "Phase 13S"
    assert output["graph_type"] == "StateGraph"
    assert output["release_ready"] is True

    sys.path.insert(0, str(GENERATED_ROOT))
    from phase13s_evidence_upload_validation_app import (  # pylint: disable=import-outside-toplevel
        EvidenceUploadRequest,
        validate_evidence_upload,
    )

    valid_request = EvidenceUploadRequest(
        dispute_case_id="CASE-13S-001",
        transaction_id="TXN-13S-000001",
        evidence_type="merchant_receipt",
        filename="receipt.pdf",
        content_sha256="a" * 64,
        content_size_bytes=2048,
        uploaded_by="customer",
    )
    result = validate_evidence_upload(valid_request)
    assert result.accepted is True
    assert result.validation_status == "ACCEPTED"
    assert result.evidence_id.startswith("EVD-")
    assert result.risk_flags == []

    rejected_request = valid_request.model_copy(update={"filename": "receipt.exe"})
    rejected = validate_evidence_upload(rejected_request)
    assert rejected.accepted is False
    assert rejected.validation_status == "REJECTED"
    assert "UNSUPPORTED_FILE_EXTENSION" in rejected.risk_flags

    with pytest_raises_validation_error():
        EvidenceUploadRequest(
            dispute_case_id="CASE-13S-001",
            transaction_id="TXN-13S-000001",
            evidence_type="merchant_receipt",
            filename="receipt.pdf",
            content_sha256="not-a-sha",
            content_size_bytes=2048,
            uploaded_by="customer",
        )

    traceability = json.loads(
        (ARTIFACT_DIR / "requirement_traceability_matrix.json").read_text(
            encoding="utf-8"
        )
    )
    mapping = traceability["mappings"][0]
    assert mapping["requirement_id"] == "REQ-13S-EVIDENCE-UPLOAD-VALIDATION"
    assert "contracts.py" in " ".join(mapping["code_files"])
    assert "tests/test_phase13s_agent_owned_application_generation.py" in mapping["test_files"]


class pytest_raises_validation_error:
    def __enter__(self) -> None:
        return None

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object,
    ) -> bool:
        assert exc_type is not None
        assert issubclass(exc_type, ValidationError)
        return True
