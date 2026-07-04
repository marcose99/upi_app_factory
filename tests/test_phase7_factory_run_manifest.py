from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any


def load_validator_module() -> ModuleType:
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "validate_factory_run_manifest.py"
    spec = importlib.util.spec_from_file_location("validate_factory_run_manifest", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def create_valid_run(tmp_path: Path) -> Path:
    run_dir = tmp_path / "workspace" / "runs" / "unit_run"
    generated_dir = run_dir / "generated"
    generated_dir.mkdir(parents=True)
    generated_file = generated_dir / "artifact.txt"
    generated_file.write_text("deterministic generated artifact\n", encoding="utf-8")

    requirements = [{"id": "REQ-P7-001", "title": "Traceability", "description": "Trace generated artifacts."}]
    policies = [{"id": "POL-EVIDENCE-LEDGER", "title": "Evidence", "description": "Record evidence."}]

    write_json(
        run_dir / "factory_run_manifest.json",
        {
            "schema_version": "factory.run_manifest.v1",
            "run_id": "unit_run",
            "workspace": "workspace/runs/unit_run",
            "source": {"head": "abc123"},
            "requirements": requirements,
            "policies": policies,
            "honesty_labels": [
                "MISSING_OFFICIAL_SOURCE",
                "SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL",
                "MOCK_BOUNDARY",
                "SYNTHETIC_DATA",
            ],
            "mock_boundaries": [
                "mock_upi_switch",
                "mock_core_banking",
                "mock_customer_notification",
                "mock_dispute_evidence_store",
            ],
            "validation_status": "passed",
        },
    )
    write_json(
        run_dir / "task_manifest.json",
        {
            "schema_version": "factory.task_manifest.v1",
            "honesty_labels": ["SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL"],
            "tasks": [
                {
                    "id": "TASK-P7-001",
                    "status": "completed",
                    "requirement_ids": ["REQ-P7-001"],
                    "policy_ids": ["POL-EVIDENCE-LEDGER"],
                    "evidence_refs": ["artifact_manifest.json"],
                }
            ],
        },
    )
    append_jsonl(
        run_dir / "agent_outputs.jsonl",
        {
            "agent_name": "traceability_agent",
            "requirement_ids": ["REQ-P7-001"],
            "task_ids": ["TASK-P7-001"],
            "summary": "Mapped artifact traceability.",
        },
    )
    append_jsonl(run_dir / "audit_events.jsonl", {"event_type": "RUN_STARTED"})
    write_json(
        run_dir / "validation_report.json",
        {"schema_version": "factory.validation_report.v1", "overall_status": "passed", "results": []},
    )
    (run_dir / "known_limitations.md").write_text(
        "MISSING_OFFICIAL_SOURCE\nSYNTHETIC_ENTERPRISE_WORKFLOW_MODEL\nMOCK_BOUNDARY\nSYNTHETIC_DATA\n",
        encoding="utf-8",
    )
    (run_dir / "release_readiness_report.md").write_text("ready\n", encoding="utf-8")
    write_json(
        run_dir / "artifact_manifest.json",
        {
            "schema_version": "factory.artifact_manifest.v1",
            "run_id": "unit_run",
            "artifact_count": 1,
            "artifacts": [
                {
                    "path": "generated/artifact.txt",
                    "artifact_type": "generated",
                    "sha256": sha256_file(generated_file),
                    "size_bytes": generated_file.stat().st_size,
                    "requirement_ids": ["REQ-P7-001"],
                    "task_ids": ["TASK-P7-001"],
                    "policy_ids": ["POL-EVIDENCE-LEDGER"],
                    "evidence_refs": ["artifact_manifest.json"],
                }
            ],
        },
    )
    return run_dir


def test_valid_factory_run_manifest_passes(tmp_path: Path) -> None:
    validator = load_validator_module()
    run_dir = create_valid_run(tmp_path)

    errors = validator.validate_run_dir(run_dir)

    assert errors == []


def test_generated_artifact_without_traceability_fails(tmp_path: Path) -> None:
    validator = load_validator_module()
    run_dir = create_valid_run(tmp_path)
    artifact_manifest_path = run_dir / "artifact_manifest.json"
    manifest = json.loads(artifact_manifest_path.read_text(encoding="utf-8"))
    manifest["artifacts"][0]["requirement_ids"] = []
    write_json(artifact_manifest_path, manifest)

    errors = validator.validate_run_dir(run_dir)

    assert any("generated artifact generated/artifact.txt" in error for error in errors)
    assert any("requirement_ids" in error for error in errors)
