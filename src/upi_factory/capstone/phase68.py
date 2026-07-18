from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


PHASE = "68"
SCHEMA_VERSION = "phase68-recipient-replay.v1"
PRODUCT_NAME = "UPI App Factory"
POSTURE = "certification-ready-not-certified"
DEFAULT_FIXTURE = Path("factory_governance/phase68_70/recipient_fixture")
DEFAULT_OUTPUT = Path("factory_governance/phase68_70/recipient_replay_output")

REQUIRED_FIXTURE_FILES = (
    "requirements_intake.json",
    "architecture_governance.json",
    "generated_application/generated_app_manifest.json",
    "generated_application/mock_cases.json",
    "safety_scenarios.json",
    "benchmark_summary.json",
    "evidence_index.json",
)

FORBIDDEN_CLAIM_PHRASES = (
    "officially certified",
    "certified by npci",
    "certified by rbi",
    "production ready",
    "production-ready",
    "approved for production",
)

FORBIDDEN_BOUNDARY_PHRASES = (
    "live provider",
    "openai api",
    "rbi api",
    "npci api",
    "bank api",
    "psp api",
    "card network",
    "real payment",
    "actual payment",
)


class Phase68Error(ValueError):
    """Raised when Phase 68 replay inputs fail closed."""


@dataclass(frozen=True)
class FileRecord:
    path: str
    sha256: str
    bytes: int

    def as_dict(self) -> dict[str, Any]:
        return {"path": self.path, "sha256": self.sha256, "bytes": self.bytes}


def repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise Phase68Error(f"Expected JSON object: {path}")
    return payload


def _canonical_json(data: Any) -> str:
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


def _safe_relative(path: Path, root: Path) -> str:
    resolved = path.resolve()
    root_resolved = root.resolve()
    try:
        rel = resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise Phase68Error(f"Path escapes replay root: {path}") from exc
    rel_text = rel.as_posix()
    if rel_text.startswith("../") or rel_text == ".." or rel.is_absolute():
        raise Phase68Error(f"Unsafe relative path: {rel_text}")
    return rel_text


def _display_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _assert_no_symlink(path: Path) -> None:
    for item in [path, *path.parents]:
        if item.exists() and item.is_symlink():
            raise Phase68Error(f"Symlink is not allowed: {item}")


def _fixture_files(fixture_root: Path) -> list[Path]:
    if not fixture_root.exists():
        raise Phase68Error(f"Missing fixture root: {fixture_root}")
    files: list[Path] = []
    for path in sorted(fixture_root.rglob("*")):
        _assert_no_symlink(path)
        if path.is_file():
            _safe_relative(path, fixture_root)
            files.append(path)
    return files


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_file_records(root: Path, files: Iterable[Path]) -> list[FileRecord]:
    return [
        FileRecord(path=_safe_relative(path, root), sha256=_hash_file(path), bytes=path.stat().st_size)
        for path in files
    ]


def validate_fixture(fixture_root: Path) -> dict[str, Any]:
    files = _fixture_files(fixture_root)
    present = {_safe_relative(path, fixture_root) for path in files}
    missing = [path for path in REQUIRED_FIXTURE_FILES if path not in present]
    if missing:
        raise Phase68Error(f"Missing required fixture files: {', '.join(missing)}")

    requirements = _read_json(fixture_root / "requirements_intake.json")
    architecture = _read_json(fixture_root / "architecture_governance.json")
    generated = _read_json(fixture_root / "generated_application" / "generated_app_manifest.json")
    safety = _read_json(fixture_root / "safety_scenarios.json")
    benchmark = _read_json(fixture_root / "benchmark_summary.json")
    evidence = _read_json(fixture_root / "evidence_index.json")
    cases = _read_json(fixture_root / "generated_application" / "mock_cases.json")

    text = "\n".join(path.read_text(encoding="utf-8").lower() for path in files)
    for phrase in FORBIDDEN_CLAIM_PHRASES:
        if phrase in text:
            raise Phase68Error(f"Unsupported production/certification claim found: {phrase}")

    for phrase in FORBIDDEN_BOUNDARY_PHRASES:
        if phrase in text and "disabled" not in text:
            raise Phase68Error(f"Mock-boundary violation found: {phrase}")

    if requirements.get("data_policy") != "fictional-data-only":
        raise Phase68Error("Requirements intake must preserve fictional-data-only policy")
    if architecture.get("certification_posture") != POSTURE:
        raise Phase68Error("Architecture governance must preserve certification-ready-not-certified posture")
    if generated.get("uses_live_provider_access") is not False:
        raise Phase68Error("Generated application inspection must not use live provider access")
    if cases.get("fictional_data_only") is not True:
        raise Phase68Error("Generated application fixture must be fictional-data-only")
    if safety.get("fail_closed_expected") is not True:
        raise Phase68Error("Safety scenarios must be fail-closed")
    if benchmark.get("runtime_dependencies") != ["python-stdlib"]:
        raise Phase68Error("Benchmark must remain stdlib/offline")
    if evidence.get("original_ignored_workspace_required") is not False:
        raise Phase68Error("Evidence verification must not require ignored workspace")

    return {
        "requirements": requirements,
        "architecture": architecture,
        "generated_application": generated,
        "safety": safety,
        "benchmark": benchmark,
        "evidence": evidence,
        "cases": cases,
        "fixture_records": [record.as_dict() for record in build_file_records(fixture_root, files)],
    }


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_canonical_json(data), encoding="utf-8")


def _copy_fixture(fixture_root: Path, payload_root: Path) -> list[FileRecord]:
    copied: list[Path] = []
    for source in _fixture_files(fixture_root):
        rel = _safe_relative(source, fixture_root)
        target = payload_root / rel
        _assert_no_symlink(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        copied.append(target)
    return build_file_records(payload_root, copied)


def _payload_record_dicts(records: Iterable[FileRecord]) -> list[dict[str, Any]]:
    return [
        {"path": f"payload/{record.path}", "sha256": record.sha256, "bytes": record.bytes}
        for record in records
    ]


def _handoff_steps() -> list[dict[str, Any]]:
    return [
        {
            "step": "requirements_intake",
            "status": "demonstrated",
            "artifact": "payload/requirements_intake.json",
        },
        {
            "step": "architecture_governance_explanation",
            "status": "demonstrated",
            "artifact": "payload/architecture_governance.json",
        },
        {
            "step": "generated_application_inspection",
            "status": "demonstrated",
            "artifact": "payload/generated_application/generated_app_manifest.json",
        },
        {"step": "safety_scenarios", "status": "demonstrated", "artifact": "payload/safety_scenarios.json"},
        {"step": "benchmark_summary", "status": "demonstrated", "artifact": "payload/benchmark_summary.json"},
        {"step": "evidence_verification", "status": "demonstrated", "artifact": "content_manifest.json"},
        {"step": "application_download_handoff", "status": "demonstrated", "artifact": "handoff_bundle.zip"},
    ]


def run_recipient_replay(
    *,
    project_root: Path | None = None,
    fixture_root: Path | None = None,
    output_root: Path | None = None,
) -> dict[str, Any]:
    root = (project_root or repository_root()).resolve()
    fixture = (fixture_root or root / DEFAULT_FIXTURE).resolve()
    output = (output_root or root / DEFAULT_OUTPUT).resolve()
    _assert_no_symlink(fixture)
    _assert_no_symlink(output)

    validation = validate_fixture(fixture)
    if output.exists():
        shutil.rmtree(output)
    payload_root = output / "payload"
    payload_records = _copy_fixture(fixture, payload_root)

    manifest_without_hash = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "product": PRODUCT_NAME,
        "status": "PASS",
        "mode": "offline_reproducible_recipient_replay",
        "data_policy": "fictional-data-only",
        "certification_posture": POSTURE,
        "official_certification_claimed": False,
        "production_readiness_claimed": False,
        "network_required": False,
        "docker_required": False,
        "credentials_required": False,
        "openai_access_required": False,
        "live_provider_access_required": False,
        "original_ignored_workspace_required": False,
        "runtime_dependencies": ["python-stdlib"],
        "mock_boundary": "deterministic-local-mocks-only",
        "fail_closed_controls": [
            "manifest_hash_verification",
            "payload_hash_verification",
            "path_traversal_rejection",
            "symlink_rejection",
            "unsupported_claim_rejection",
            "mock_boundary_rejection",
        ],
        "recipient_steps": _handoff_steps(),
        "fixture_records": validation["fixture_records"],
        "payload_records": _payload_record_dicts(payload_records),
    }
    manifest_hash = hashlib.sha256(_canonical_json(manifest_without_hash).encode("utf-8")).hexdigest()
    manifest = {**manifest_without_hash, "manifest_sha256": manifest_hash}
    _write_json(output / "content_manifest.json", manifest)

    verifier = {
        "schema_version": "phase68-independent-verifier.v1",
        "verifier": "scripts/validate_phase68_reproducible_evaluator_recipient.py",
        "expected_manifest_sha256": manifest_hash,
        "expected_status": "PASS",
    }
    _write_json(output / "independent_verifier.json", verifier)

    bundle_path = output / "handoff_bundle.zip"
    bundle_inputs = [output / "content_manifest.json", output / "independent_verifier.json"]
    bundle_inputs.extend(sorted(payload_root.rglob("*")))
    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in bundle_inputs:
            if path.is_file():
                archive.write(path, _safe_relative(path, output))

    bundle_sha256 = _hash_file(bundle_path)
    result = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "status": "PASS",
        "output_root": _display_path(output, root),
        "content_manifest": _display_path(output / "content_manifest.json", root),
        "handoff_bundle": _display_path(bundle_path, root),
        "handoff_bundle_sha256": bundle_sha256,
        "certification_posture": POSTURE,
        "fictional_data_only": True,
        "official_certification_claimed": False,
        "production_readiness_claimed": False,
        "live_provider_calls_performed": False,
    }
    _write_json(output / "recipient_replay_result.json", result)
    return result


def verify_manifest(manifest_path: Path) -> dict[str, Any]:
    manifest = _read_json(manifest_path)
    expected_hash = manifest.get("manifest_sha256")
    without_hash = dict(manifest)
    without_hash.pop("manifest_sha256", None)
    actual_hash = hashlib.sha256(_canonical_json(without_hash).encode("utf-8")).hexdigest()
    if expected_hash != actual_hash:
        raise Phase68Error("Manifest hash mismatch")

    manifest_root = manifest_path.parent.resolve()
    if manifest.get("status") != "PASS":
        raise Phase68Error("Manifest status must be PASS")
    if manifest.get("data_policy") != "fictional-data-only":
        raise Phase68Error("Manifest must preserve fictional-data-only")
    if manifest.get("certification_posture") != POSTURE:
        raise Phase68Error("Manifest must preserve certification-ready-not-certified posture")
    for key in (
        "official_certification_claimed",
        "production_readiness_claimed",
        "network_required",
        "docker_required",
        "credentials_required",
        "openai_access_required",
        "live_provider_access_required",
        "original_ignored_workspace_required",
    ):
        if manifest.get(key) is not False:
            raise Phase68Error(f"Manifest must keep {key} false")

    payload_records = manifest.get("payload_records")
    if not isinstance(payload_records, list) or not payload_records:
        raise Phase68Error("Manifest must contain payload records")
    for record in payload_records:
        if not isinstance(record, dict):
            raise Phase68Error("Payload record must be an object")
        rel = record.get("path")
        if not isinstance(rel, str) or rel.startswith("/") or ".." in Path(rel).parts:
            raise Phase68Error(f"Unsafe payload path: {rel}")
        path = manifest_root / rel
        _assert_no_symlink(path)
        _safe_relative(path, manifest_root)
        if not path.is_file():
            raise Phase68Error(f"Missing payload file: {rel}")
        if _hash_file(path) != record.get("sha256"):
            raise Phase68Error(f"Payload hash mismatch: {rel}")
        if path.stat().st_size != record.get("bytes"):
            raise Phase68Error(f"Payload byte-size mismatch: {rel}")

    text = "\n".join(
        (manifest_root / record["path"]).read_text(encoding="utf-8").lower()
        for record in payload_records
        if str(record["path"]).endswith(".json")
    )
    for phrase in FORBIDDEN_CLAIM_PHRASES:
        if phrase in text:
            raise Phase68Error(f"Unsupported claim found in payload: {phrase}")
    if "fictional" not in text:
        raise Phase68Error("Payload must explicitly use fictional data")

    return {
        "schema_version": "phase68-independent-verifier-result.v1",
        "phase": PHASE,
        "status": "PASS",
        "manifest": str(manifest_path),
        "manifest_sha256": actual_hash,
        "verified_payload_records": len(payload_records),
    }


def main_replay(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Phase 68 offline recipient replay.")
    parser.add_argument("--project-root", type=Path, default=repository_root())
    parser.add_argument("--fixture-root", type=Path)
    parser.add_argument("--output-root", type=Path)
    args = parser.parse_args(argv)
    result = run_recipient_replay(
        project_root=args.project_root,
        fixture_root=args.fixture_root,
        output_root=args.output_root,
    )
    print(_canonical_json(result), end="")
    return 0


def main_verify(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Phase 68 reproducible evaluator recipient replay.")
    parser.add_argument("--manifest", type=Path, default=repository_root() / DEFAULT_OUTPUT / "content_manifest.json")
    parser.add_argument("--project-root", type=Path, default=repository_root())
    args = parser.parse_args(argv)
    try:
        root = args.project_root.resolve()
        required_paths = [
            root / "scripts" / "run_phase68_recipient_replay.py",
            root / "scripts" / "validate_phase68_reproducible_evaluator_recipient.py",
            root / "docs" / "capstone" / "phase68_70" / "phase68_recipient_replay.md",
            root / "docs" / "capstone" / "phase68_70" / "reproducible_evaluator_recipient.md",
            root / DEFAULT_FIXTURE,
        ]
        missing = [str(path) for path in required_paths if not path.exists()]
        if missing:
            raise Phase68Error(f"Missing required Phase 68 artifact(s): {', '.join(missing)}")
        validate_fixture(root / DEFAULT_FIXTURE)
        manifest_path = args.manifest
        if not manifest_path.exists():
            with tempfile.TemporaryDirectory() as tmp:
                replay = run_recipient_replay(
                    project_root=root,
                    fixture_root=root / DEFAULT_FIXTURE,
                    output_root=Path(tmp) / "recipient_replay",
                )
                result = verify_manifest(Path(replay["content_manifest"]))
        else:
            result = verify_manifest(manifest_path)
    except (OSError, json.JSONDecodeError, Phase68Error) as exc:
        print(_canonical_json({"schema_version": "phase68-independent-verifier-result.v1", "status": "FAIL", "error": str(exc)}), end="")
        return 1
    print(_canonical_json(result), end="")
    return 0
