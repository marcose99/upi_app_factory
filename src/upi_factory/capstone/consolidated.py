from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from tools.factory_control_plane.manifest import load_manifest
from upi_factory.capstone.phase68 import run_recipient_replay, verify_manifest
from upi_factory.capstone.phase69 import run_phase69_demonstration, validate_phase69_demonstration
from upi_factory.capstone.phase70 import run_phase70_validation


SCHEMA_VERSION = "phase68-70-consolidated-capstone.v1"
CAMPAIGN_ID = "phase68_70_consolidated_capstone_v1"
CAMPAIGN_MANIFEST = Path("config/control_plane/campaigns/phase68_70_consolidated_capstone.json")
CERTIFICATION_POSTURE = "certification-ready-not-certified"
PRODUCT_NAME = "UPI App Factory"
REPOSITORY_ID = "upi_app_factory"
FORBIDDEN_CLAIMS = (
    "production ready",
    "production-ready",
    "officially certified",
    "certified by npci",
    "certified by rbi",
    "approved for production",
)
REQUIRED_TRACKED_PATHS = (
    "bin/upi-app-factory-capstone",
    "config/control_plane/campaigns/phase68_70_consolidated_capstone.json",
    "docs/adr/ADR-0068-consolidated-phases-68-70-capstone.md",
    "docs/capstone/phase68_70/README.md",
    "scripts/run_phase68_70_consolidated_capstone.py",
    "scripts/validate_phase68_70_consolidated_capstone.py",
    "schemas/phase68_70/consolidated_capstone.schema.json",
    "schemas/phase68_70/evidence_integrity.schema.json",
    "policies/phase68_70/mock_boundary_policy.json",
    "policies/phase68_70/operator_accountability_policy.json",
    "prompts/phase68_70/reusable_evaluator_prompt.md",
    "prompts/phase68_70/operator_capstone_prompt.md",
)


class ConsolidatedCapstoneError(ValueError):
    """Raised when the consolidated Phase 68-70 capstone fails closed."""


@dataclass(frozen=True)
class FileRecord:
    path: str
    sha256: str
    bytes: int

    def as_dict(self) -> dict[str, Any]:
        return {"path": self.path, "sha256": self.sha256, "bytes": self.bytes}


def repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def canonical_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def compact_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def assert_no_symlink(path: Path) -> None:
    for item in [path, *path.parents]:
        if item.exists() and item.is_symlink():
            raise ConsolidatedCapstoneError(f"Symlink is not allowed: {item}")


def safe_child(root: Path, *parts: str) -> Path:
    assert_no_symlink(root)
    resolved_root = root.resolve()
    candidate = resolved_root.joinpath(*parts).resolve()
    try:
        candidate.relative_to(resolved_root)
    except ValueError as exc:
        raise ConsolidatedCapstoneError(f"Path escapes runtime root: {candidate}") from exc
    assert_no_symlink(candidate)
    return candidate


def relative_to(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(value), encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ConsolidatedCapstoneError(f"Expected JSON object: {path}")
    return value


def file_records(root: Path, paths: Iterable[Path]) -> list[FileRecord]:
    records: list[FileRecord] = []
    for path in sorted(paths):
        if not path.is_file() or path.is_symlink():
            raise ConsolidatedCapstoneError(f"Unsafe or missing evidence file: {path}")
        records.append(FileRecord(relative_to(path, root), hash_file(path), path.stat().st_size))
    return records


def runtime_files(runtime_root: Path) -> list[Path]:
    if not runtime_root.is_dir():
        return []
    files: list[Path] = []
    for path in runtime_root.rglob("*"):
        assert_no_symlink(path)
        if path.is_file():
            files.append(path)
    return files


def tracked_file_records(project_root: Path) -> list[dict[str, Any]]:
    paths = [project_root / item for item in REQUIRED_TRACKED_PATHS]
    missing = [relative_to(path, project_root) for path in paths if not path.is_file()]
    if missing:
        raise ConsolidatedCapstoneError(f"Missing tracked deliverable(s): {', '.join(missing)}")
    return [record.as_dict() for record in file_records(project_root, paths)]


def assert_no_forbidden_claims(payload: Any) -> None:
    text = json.dumps(payload, sort_keys=True).lower() if not isinstance(payload, str) else payload.lower()
    for phrase in FORBIDDEN_CLAIMS:
        if phrase in text:
            raise ConsolidatedCapstoneError(f"Forbidden claim found: {phrase}")


def verify_campaign_manifest(project_root: Path) -> dict[str, Any]:
    manifest_path = project_root / CAMPAIGN_MANIFEST
    manifest = load_manifest(manifest_path, project_root)
    raw = read_json(manifest_path)
    activity_ids = [activity.id for activity in manifest.activities]
    required = [
        "phase68_recipient_replay",
        "phase68_recipient_replay_verification",
        "phase69_control_plane_portal_checkpoint",
        "phase70_multi_domain_application_portfolio",
        "phase68_70_evidence_integrity_checkpoint",
    ]
    missing = [item for item in required if item not in activity_ids]
    if missing:
        raise ConsolidatedCapstoneError(f"Manifest missing capstone activities: {', '.join(missing)}")
    by_id = {activity.id: activity for activity in manifest.activities}
    if list(by_id["phase68_recipient_replay_verification"].dependencies) != ["phase68_recipient_replay"]:
        raise ConsolidatedCapstoneError("Phase 68 verification must depend on Phase 68 replay")
    if "phase68_recipient_replay_verification" not in by_id["phase69_control_plane_portal_checkpoint"].dependencies:
        raise ConsolidatedCapstoneError("Phase 69 checkpoint must depend on Phase 68 verification")
    if "phase69_control_plane_portal_checkpoint" not in by_id["phase70_multi_domain_application_portfolio"].dependencies:
        raise ConsolidatedCapstoneError("Phase 70 portfolio must depend on Phase 69 checkpoint")
    if "phase70_multi_domain_application_portfolio" not in by_id["phase68_70_evidence_integrity_checkpoint"].dependencies:
        raise ConsolidatedCapstoneError("Evidence checkpoint must depend on Phase 70")
    metadata = raw.get("metadata", {})
    protected = set(raw.get("approvals", {}).get("human", []))
    if isinstance(metadata, dict):
        protected |= set(metadata.get("protected_actions", []))
    required_protected = {
        "production_deployment",
        "public_release",
        "real_payment_rail_access",
        "real_customer_data_access",
        "certification_claim",
        "live_llm_runtime",
    }
    if not required_protected.issubset(protected):
        raise ConsolidatedCapstoneError("Manifest does not explicitly protect all required human-gated actions")
    activity_phases = metadata.get("activity_phases", {}) if isinstance(metadata, dict) else {}
    phases = {str(item) for item in activity_phases.values()} if isinstance(activity_phases, dict) else set()
    if not {"68", "69", "70"}.issubset(phases):
        raise ConsolidatedCapstoneError("Manifest must identify Phase 68, 69 and 70 activities")
    return {
        "path": CAMPAIGN_MANIFEST.as_posix(),
        "campaign_id": manifest.campaign_id,
        "sha256": manifest.digest,
        "activity_ids": activity_ids,
        "protected_actions": sorted(protected),
    }


def build_event(sequence: int, phase: str, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    event = {
        "sequence": sequence,
        "phase": phase,
        "event_type": event_type,
        "payload": payload,
    }
    event["event_hash"] = sha256_bytes(compact_json(event))
    return event


def run_consolidated_capstone(*, project_root: Path | None = None, runtime_root: Path | None = None) -> dict[str, Any]:
    root = (project_root or repository_root()).resolve()
    if runtime_root is None:
        runtime_context = tempfile.TemporaryDirectory(prefix="upi_phase68_70_capstone_")
        runtime = Path(runtime_context.name).resolve()
    else:
        runtime_context = None
        runtime = runtime_root.resolve()
    try:
        assert_no_symlink(runtime)
        if runtime == root or root in runtime.parents:
            raise ConsolidatedCapstoneError("Runtime root must be isolated outside the repository worktree")
        if runtime.exists():
            shutil.rmtree(runtime)
        runtime.mkdir(parents=True, exist_ok=True)

        manifest = verify_campaign_manifest(root)
        events: list[dict[str, Any]] = [
            build_event(1, "68-70", "capstone_started", {"campaign_id": CAMPAIGN_ID, "runtime_root": str(runtime)})
        ]

        phase68_output = safe_child(runtime, "phase68", "recipient_replay")
        phase68 = run_recipient_replay(project_root=root, output_root=phase68_output)
        phase68_verify = verify_manifest(phase68_output / "content_manifest.json")
        events.append(
            build_event(
                2,
                "68",
                "recipient_replay_verified",
                {
                    "status": phase68_verify["status"],
                    "manifest_sha256": phase68_verify["manifest_sha256"],
                    "bundle_sha256": phase68["handoff_bundle_sha256"],
                },
            )
        )

        phase69 = run_phase69_demonstration(
            project_root=root,
            state_root=safe_child(runtime, "phase69", "control_plane_state"),
            write_evidence=False,
        )
        phase69_validate = validate_phase69_demonstration(project_root=root)
        if phase69.get("status") != "PASS" or phase69_validate.get("status") != "PASS":
            raise ConsolidatedCapstoneError("Phase 69 control-plane portal demonstration failed")
        events.append(
            build_event(
                3,
                "69",
                "control_plane_portal_demonstrated",
                {
                    "status": phase69["status"],
                    "validation_status": phase69_validate["status"],
                    "control_plane_event_count": phase69["portal"]["control_plane"]["event_count"],
                    "demonstration_sha256": phase69["demonstration_sha256"],
                },
            )
        )

        phase70 = run_phase70_validation(project_root=root, runtime_root=safe_child(runtime, "phase70"))
        if phase70.get("status") != "PASS":
            raise ConsolidatedCapstoneError("Phase 70 multi-domain portfolio validation failed")
        events.append(
            build_event(
                4,
                "70",
                "multi_domain_portfolio_validated",
                {
                    "status": phase70["status"],
                    "profile_count": phase70["profile_count"],
                    "portfolio_sha256": phase70["portfolio_sha256"],
                    "minimum_depth_score": phase70["depth"]["minimum_score"],
                },
            )
        )

        evidence_files = runtime_files(runtime)
        records = [record.as_dict() for record in file_records(runtime, evidence_files)]
        events.append(
            build_event(
                5,
                "68-70",
                "evidence_integrity_recorded",
                {"runtime_file_count": len(records), "tracked_file_count": len(REQUIRED_TRACKED_PATHS)},
            )
        )

        summary_without_hash = {
            "schema_version": SCHEMA_VERSION,
            "status": "PASS",
            "product_name": PRODUCT_NAME,
            "repository_id": REPOSITORY_ID,
            "campaign_id": CAMPAIGN_ID,
            "certification_posture": CERTIFICATION_POSTURE,
            "official_certification_claimed": False,
            "production_readiness_claimed": False,
            "fictional_data_only": True,
            "real_payment_calls": "disabled",
            "runtime_llm_calls": 0,
            "network_required": False,
            "manifest": manifest,
            "phase_contracts": {
                "phase68": {
                    "status": phase68_verify["status"],
                    "recipient_replay_result": phase68,
                    "verified_payload_records": phase68_verify["verified_payload_records"],
                },
                "phase69": {
                    "status": phase69["status"],
                    "validation_status": phase69_validate["status"],
                    "checked_contracts": phase69_validate["checked_contracts"],
                },
                "phase70": {
                    "status": phase70["status"],
                    "profile_count": phase70["profile_count"],
                    "minimum_depth_score": phase70["depth"]["minimum_score"],
                    "portfolio_sha256": phase70["portfolio_sha256"],
                },
            },
            "trust_boundaries": {
                "external_payment_ecosystems": "mocked-or-simulated-only",
                "bank_psp_npci_rbi_card_network_calls": "disabled",
                "recipient_replay_requires_ignored_workspace": False,
                "portal_progress_source": "control-plane-events",
                "downloads": "manifest-hash-and-payload-hash-verified",
            },
            "events": events,
            "evidence_records": records,
            "tracked_deliverable_records": tracked_file_records(root),
        }
        summary_hash = sha256_bytes(compact_json(summary_without_hash))
        summary = {**summary_without_hash, "summary_sha256": summary_hash}
        write_json(safe_child(runtime, "events.json"), events)
        write_json(safe_child(runtime, "evidence_integrity.json"), {"records": records})
        write_json(safe_child(runtime, "final_summary.json"), summary)
        assert_no_forbidden_claims(summary)
        return summary
    finally:
        if runtime_context is not None:
            runtime_context.cleanup()


def validate_consolidated_capstone(
    *,
    project_root: Path | None = None,
    runtime_root: Path | None = None,
    summary_path: Path | None = None,
) -> dict[str, Any]:
    root = (project_root or repository_root()).resolve()
    errors: list[str] = []
    checked: list[str] = []

    def check(name: str, func: Any) -> Any:
        try:
            value = func()
            checked.append(name)
            return value
        except Exception as exc:
            errors.append(f"{name}: {exc}")
            return None

    manifest = check("repository_native_control_plane_linkage", lambda: verify_campaign_manifest(root))
    check("tracked_deliverables", lambda: tracked_file_records(root))
    check("phase68_contract", lambda: verify_manifest(root / "factory_governance/phase68_70/recipient_replay_output/content_manifest.json"))
    check("phase69_contract", lambda: validate_phase69_demonstration(project_root=root))
    phase70 = check("phase70_contract", lambda: run_phase70_validation(project_root=root))

    docs_text = "\n".join(
        (root / path).read_text(encoding="utf-8")
        for path in (
            "docs/capstone/phase68_70/README.md",
            "docs/adr/ADR-0068-consolidated-phases-68-70-capstone.md",
        )
        if (root / path).is_file()
    )
    lowered_docs = docs_text.lower()
    if "workspace/" in lowered_docs and "not required" not in lowered_docs and "does not require" not in lowered_docs:
        errors.append("documentation suggests an ignored workspace dependency")
    if phase70 and (phase70.get("profile_count") != 6 or phase70.get("depth", {}).get("minimum_score", 0) < 82):
        errors.append("multi-domain depth is below the consolidated capstone contract")
    if manifest and CAMPAIGN_ID != manifest["campaign_id"]:
        errors.append("manifest campaign id does not match consolidated capstone")

    if summary_path is not None:
        summary = check("runtime_summary", lambda: read_json(summary_path))
    elif runtime_root is not None and (runtime_root / "final_summary.json").is_file():
        summary = check("runtime_summary", lambda: read_json(runtime_root / "final_summary.json"))
    else:
        summary = None
    if summary:
        expected = summary.get("summary_sha256")
        without = dict(summary)
        without.pop("summary_sha256", None)
        if expected != sha256_bytes(compact_json(without)):
            errors.append("runtime summary hash mismatch")
        if summary.get("runtime_llm_calls") != 0:
            errors.append("runtime LLM calls must be zero")
        if summary.get("trust_boundaries", {}).get("portal_progress_source") != "control-plane-events":
            errors.append("portal progress is not sourced from control-plane events")
        if summary.get("trust_boundaries", {}).get("recipient_replay_requires_ignored_workspace") is not False:
            errors.append("recipient replay depends on ignored workspace")
        if runtime_root is not None:
            for record in summary.get("evidence_records", []):
                rel = record.get("path")
                if not isinstance(rel, str) or rel.startswith("/") or ".." in Path(rel).parts:
                    errors.append(f"unsafe evidence path in runtime summary: {rel}")
                    continue
                path = safe_child(runtime_root, rel)
                if not path.is_file() or hash_file(path) != record.get("sha256") or path.stat().st_size != record.get("bytes"):
                    errors.append(f"evidence integrity mismatch: {rel}")
    check("forbidden_claim_scan", lambda: assert_no_forbidden_claims({"docs": docs_text, "summary": summary or {}}))

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "PASS" if not errors else "FAIL",
        "campaign_id": CAMPAIGN_ID,
        "checked_contracts": checked,
        "errors": errors,
    }


def main_run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the offline Phase 68-70 consolidated capstone.")
    parser.add_argument("--project-root", type=Path, default=repository_root())
    parser.add_argument("--runtime-root", type=Path)
    args = parser.parse_args(argv)
    try:
        result = run_consolidated_capstone(project_root=args.project_root, runtime_root=args.runtime_root)
    except Exception as exc:
        print(canonical_json({"schema_version": SCHEMA_VERSION, "status": "FAIL", "error": str(exc)}), end="")
        return 1
    print(canonical_json(result), end="")
    return 0


def main_validate(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the Phase 68-70 consolidated capstone.")
    parser.add_argument("--project-root", type=Path, default=repository_root())
    parser.add_argument("--runtime-root", type=Path)
    parser.add_argument("--summary", type=Path)
    args = parser.parse_args(argv)
    try:
        result = validate_consolidated_capstone(
            project_root=args.project_root,
            runtime_root=args.runtime_root,
            summary_path=args.summary,
        )
    except Exception as exc:
        print(canonical_json({"schema_version": SCHEMA_VERSION, "status": "FAIL", "error": str(exc)}), end="")
        return 1
    print(canonical_json(result), end="")
    return 0 if result["status"] == "PASS" else 1
