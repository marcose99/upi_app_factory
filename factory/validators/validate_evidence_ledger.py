from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any


GENESIS_HASH = "0" * 64
REQUIRED_FIELDS = ("evidence_id", "source_type", "title", "status")
HASH_FIELDS = frozenset({"record_sha256", "previous_record_sha256"})


def canonical_record_payload(record: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if key not in HASH_FIELDS}


def record_sha256(record: dict[str, Any], previous_record_sha256: str) -> str:
    material = {
        "record": canonical_record_payload(record),
        "previous_record_sha256": previous_record_sha256,
    }
    return hashlib.sha256(
        json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_evidence_ledger(path: Path = Path("evidence/evidence_ledger.jsonl")) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    verified_records = 0
    seen_evidence_ids: set[str] = set()
    previous_record_hash = GENESIS_HASH
    previous_sequence = 0
    if not path.exists():
        errors.append("evidence ledger missing")
    else:
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"invalid json line {line_no}: {exc}")
                continue
            if not isinstance(record, dict):
                errors.append(f"line {line_no} must be a JSON object")
                continue
            for field in REQUIRED_FIELDS:
                if field not in record:
                    errors.append(f"line {line_no} missing {field}")
            evidence_id = str(record.get("evidence_id", ""))
            if evidence_id:
                if evidence_id in seen_evidence_ids:
                    errors.append(f"duplicate evidence_id detected: {evidence_id}")
                seen_evidence_ids.add(evidence_id)
            sequence = int(record.get("sequence", line_no))
            if sequence != previous_sequence + 1:
                errors.append(
                    f"line {line_no} sequence {sequence} breaks append-only order after {previous_sequence}"
                )
            previous_sequence = sequence
            claimed_previous = str(record.get("previous_record_sha256", previous_record_hash))
            if claimed_previous != previous_record_hash:
                errors.append(
                    f"line {line_no} previous_record_sha256 mismatch: expected {previous_record_hash}"
                )
            computed_hash = record_sha256(record, previous_record_hash)
            claimed_hash = record.get("record_sha256")
            if claimed_hash is not None:
                if str(claimed_hash) != computed_hash:
                    errors.append(f"line {line_no} record_sha256 mismatch")
            else:
                warnings.append(
                    f"line {line_no} uses legacy evidence-ledger format without record_sha256"
                )
            previous_record_hash = computed_hash
            artifacts = record.get("artifacts", [])
            if artifacts not in (None, []) and not isinstance(artifacts, list):
                errors.append(f"line {line_no} artifacts must be a list")
            for artifact_index, artifact in enumerate(artifacts or [], start=1):
                if not isinstance(artifact, dict):
                    errors.append(f"line {line_no} artifact {artifact_index} must be a JSON object")
                    continue
                artifact_path = artifact.get("path")
                if not isinstance(artifact_path, str) or not artifact_path.strip():
                    errors.append(f"line {line_no} artifact {artifact_index} missing path")
                    continue
                artifact_candidate = Path(artifact_path)
                if artifact_candidate.is_absolute() or ".." in artifact_candidate.parts:
                    errors.append(f"line {line_no} artifact {artifact_index} path traversal rejected")
                    continue
                resolved = (path.parent.parent / artifact_candidate).resolve()
                if not resolved.exists():
                    errors.append(
                        f"line {line_no} artifact {artifact_index} missing file: {artifact_candidate.as_posix()}"
                    )
                    continue
                expected_sha = artifact.get("sha256")
                if expected_sha is not None and str(expected_sha) != sha256_file(resolved):
                    errors.append(
                        f"line {line_no} artifact {artifact_index} sha256 mismatch: {artifact_candidate.as_posix()}"
                    )
            verified_records += 1
    return {
        "passed": not errors,
        "path": path.as_posix(),
        "verified_records": verified_records,
        "errors": errors,
        "warnings": warnings,
        "last_record_sha256": previous_record_hash if verified_records else None,
    }


def main() -> int:
    payload = validate_evidence_ledger()
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 1 if payload["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
