from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parents[1]
AUDIT_PATH = (
    ROOT
    / "workspace"
    / "factory_generated"
    / "upi_dispute_resolution"
    / "lifecycle_artifacts"
    / "phase13i"
    / "release_readiness_audit.json"
)
ADAPTER_RUN_ROOT = (
    ROOT
    / "workspace"
    / "factory_generated"
    / "upi_dispute_resolution"
    / "generation_runs"
    / "first_governed_generation_run_001"
)
ADAPTER_REPORT_PATH = ADAPTER_RUN_ROOT / "agent_adapter_execution_report.json"
ADAPTER_LEDGER_PATHS = [
    ADAPTER_RUN_ROOT / "agent_runtime_ledgers" / "adapter_capability_ledger.jsonl",
    ADAPTER_RUN_ROOT / "agent_runtime_ledgers" / "adapter_execution_ledger.jsonl",
    ADAPTER_RUN_ROOT / "agent_runtime_ledgers" / "handoff_ledger.jsonl",
    ADAPTER_RUN_ROOT / "agent_runtime_ledgers" / "runtime_event_ledger.jsonl",
    ADAPTER_RUN_ROOT / "agent_runtime_ledgers" / "tool_execution_ledger.jsonl",
]


class FileSnapshot(NamedTuple):
    path: Path
    content: bytes | None


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=True)


def snapshot_files(paths: list[Path]) -> list[FileSnapshot]:
    return [
        FileSnapshot(path=path, content=path.read_bytes() if path.exists() else None)
        for path in paths
    ]


def restore_files(snapshots: list[FileSnapshot]) -> None:
    for snapshot in snapshots:
        if snapshot.content is None:
            snapshot.path.unlink(missing_ok=True)
        else:
            snapshot.path.parent.mkdir(parents=True, exist_ok=True)
            snapshot.path.write_bytes(snapshot.content)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_path_is_clean(path: Path) -> bool:
    relative_path = str(path.relative_to(ROOT))
    result = subprocess.run(
        ["git", "status", "--short", "--", relative_path],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout == ""


def test_phase13i_audit_and_validator_pass() -> None:
    tracked_paths = [ADAPTER_REPORT_PATH, *ADAPTER_LEDGER_PATHS]
    snapshots = snapshot_files(tracked_paths)
    baseline_hashes = {
        path: file_sha256(path) if path.exists() else None
        for path in tracked_paths
    }
    result: subprocess.CompletedProcess[str] | None = None
    command_failure: Exception | None = None
    try:
        run_command([sys.executable, "scripts/run_phase13i_release_readiness_audit.py"])
        result = run_command([sys.executable, "scripts/validate_phase13i_release_readiness.py"])
    except Exception as exc:
        command_failure = exc
    finally:
        restore_files(snapshots)

    for path in tracked_paths:
        baseline_hash = baseline_hashes[path]
        if baseline_hash is None:
            assert not path.exists()
        else:
            assert path.exists()
            assert file_sha256(path) == baseline_hash
        assert git_path_is_clean(path)
    if command_failure is not None:
        raise command_failure
    assert result is not None
    assert '"passed": true' in result.stdout

def test_phase13i_evidence_is_deterministic() -> None:
    data = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    assert data["evidence_determinism"]["uses_current_commit_hash"] is False
    assert data["evidence_determinism"]["uses_wall_clock_timestamp"] is False
    assert data["baseline_tag"] == "v0.13.7-release-state-lineage-registry"


def test_phase13i_operator_handover_has_no_missing_entries() -> None:
    data = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    handover_checks = [
        item for item in data["operator_smoke_checks"] if item["command"] == "./factoryctl handover"
    ]
    assert len(handover_checks) == 1
    assert handover_checks[0]["passed"] is True
    assert handover_checks[0]["handover_missing_entries"] is False
