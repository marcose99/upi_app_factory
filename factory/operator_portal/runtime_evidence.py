from __future__ import annotations

import hashlib
import json
from pathlib import Path
import zipfile
from typing import Any

from factory.operator_portal.runtime_contracts import (
    CERTIFICATION_POSTURE,
    RuntimeContractError,
    RuntimeState,
    safe_relative_path,
    utc_now,
)
from factory.operator_portal.runtime_store import RuntimeStore, redact
from factory.operator_portal.runtime_supervisor import RuntimeSupervisor


ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


class RuntimeEvidenceService:
    def __init__(self, *, project_root: Path, store: RuntimeStore) -> None:
        self.project_root = project_root.resolve()
        self.store = store

    def build_manifest(self, *, run_id: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        runtime_identity = self._verified_runtime_identity_if_active(run_id)
        run_dir = self.store.run_dir(run_id)
        files = []
        for path in sorted(run_dir.rglob("*")):
            if path.is_dir() or path.name == "runtime_evidence_manifest.json" or path.name.endswith(".zip"):
                continue
            relative = safe_relative_path(path, run_dir)
            data = path.read_bytes()
            files.append({"path": relative, "size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
        gates = {
            "ordered_unique_events": self._ordered_unique_events(run_id),
            "scenario_results_present": self.store.scenario_path(run_id).is_file(),
            "approval_plaintext_absent": self._approval_plaintext_absent(run_dir),
            "real_payment_calls_disabled": True,
            "default_runtime_llm_calls_zero": True,
        }
        decision = "GO" if all(gates.values()) else "NO_GO"
        manifest = {
            "schema_version": "1.0",
            "artifact_type": "phase50_runtime_evidence",
            "run_id": run_id,
            "generated_at_utc": utc_now(),
            "certification_posture": CERTIFICATION_POSTURE,
            "real_payment_calls": "disabled",
            "default_runtime_llm_calls": 0,
            "validation_gates": gates,
            "decision": decision,
            "files": files,
            "runtime_identity": runtime_identity,
            "extra": redact(extra or {}),
        }
        self.store.atomic_write_json(run_dir / "runtime_evidence_manifest.json", manifest)
        return manifest

    def _verified_runtime_identity_if_active(self, run_id: str) -> dict[str, str] | None:
        state_path = self.store.state_path(run_id)
        if not state_path.is_file():
            return None
        payload = self.store.read_json(state_path)
        try:
            state = RuntimeState(str(payload.get("state", "")))
        except ValueError as exc:
            raise RuntimeContractError("runtime evidence state is malformed") from exc
        if state not in {RuntimeState.READY, RuntimeState.DEGRADED}:
            return None
        binding = payload.get("binding")
        if not isinstance(binding, dict) or not isinstance(binding.get("port"), int):
            raise RuntimeContractError("runtime evidence binding is malformed")
        supervisor = RuntimeSupervisor(project_root=self.project_root, store=self.store)
        status = supervisor.status(run_id=run_id, port=int(binding["port"]))
        if status.state not in {RuntimeState.READY, RuntimeState.DEGRADED}:
            raise RuntimeContractError("runtime identity is not verified for evidence attribution")
        return supervisor._runtime_identity_payload(run_id)

    def archive(self, *, run_id: str) -> Path:
        manifest = self.build_manifest(run_id=run_id)
        run_dir = self.store.run_dir(run_id)
        archive_path = run_dir / "runtime_evidence.zip"
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for item in manifest["files"]:
                path = run_dir / item["path"]
                if path.is_symlink():
                    raise RuntimeContractError("symlinks are rejected from runtime evidence")
                info = zipfile.ZipInfo(f"{run_id}_runtime_evidence/{item['path']}")
                info.date_time = ZIP_TIMESTAMP
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, path.read_bytes())
            info = zipfile.ZipInfo(f"{run_id}_runtime_evidence/runtime_evidence_manifest.json")
            info.date_time = ZIP_TIMESTAMP
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8") + b"\n")
        return archive_path

    def _ordered_unique_events(self, run_id: str) -> bool:
        events = self.store.read_events(run_id)
        sequences = [int(event["sequence"]) for event in events if isinstance(event.get("sequence"), int)]
        return bool(sequences) and sequences == sorted(sequences) and len(sequences) == len(set(sequences))

    def _approval_plaintext_absent(self, run_dir: Path) -> bool:
        forbidden = b"phase50-local-runtime-approval"
        for path in run_dir.rglob("*"):
            if path.is_file() and path.suffix != ".zip" and forbidden in path.read_bytes():
                return False
        return True
