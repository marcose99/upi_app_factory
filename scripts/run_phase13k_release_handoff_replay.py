#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any

APP_ID = "upi_dispute_resolution"
PHASE = "Phase 13K"
BASELINE_TAG = "v0.13.9-release-handoff-bundle-pack"
ROOT = Path(__file__).resolve().parents[1]
BUNDLE_DIR = ROOT / "workspace" / "factory_generated" / APP_ID / "release_handoff_bundle" / "phase13j"
OUT_DIR = ROOT / "workspace" / "factory_generated" / APP_ID / "lifecycle_artifacts" / "phase13k"
OUT_FILE = OUT_DIR / "release_handoff_replay_audit.json"

REQUIRED_BUNDLE_FILES = [
    "release_handoff_manifest.json",
    "README.md",
    "OPERATOR_COMMANDS.md",
    "TRUTH_BOUNDARY.md",
    "CHECKSUMS.sha256",
]
OPERATOR_COMMANDS = [
    "./factoryctl status",
    "./factoryctl adapters",
    "./factoryctl handover",
]
DOCUMENTED_COMMANDS = [
    "./factoryctl status",
    "./factoryctl adapters",
    "./factoryctl validate --quick",
    "./factoryctl validate",
    "./factoryctl portals",
    "./factoryctl handover",
    "./factoryctl logs",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_tag_present(tag: str) -> bool:
    result = subprocess.run(["git", "rev-parse", "--verify", f"refs/tags/{tag}"], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return result.returncode == 0


def read_text_if_present(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def parse_checksums(path: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    if not path.exists():
        return entries
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        parts = stripped.split(maxsplit=1)
        if len(parts) != 2:
            entries.append({"path": stripped, "expected_sha256": "", "parse_error": True})
            continue
        expected, rel_path = parts
        rel_path = rel_path.lstrip("*").strip()
        entries.append({"path": rel_path, "expected_sha256": expected, "parse_error": False})
    return entries


def verify_checksum_entries() -> list[dict[str, Any]]:
    checksums_path = BUNDLE_DIR / "CHECKSUMS.sha256"
    results: list[dict[str, Any]] = []
    for entry in parse_checksums(checksums_path):
        rel_path = str(entry["path"])
        target = ROOT / rel_path
        exists = target.exists() and target.is_file()
        actual = sha256_file(target) if exists else ""
        expected = str(entry.get("expected_sha256", ""))
        results.append(
            {
                "path": rel_path,
                "scope": "repository_root",
                "exists": exists,
                "expected_sha256": expected,
                "actual_sha256": actual,
                "matches": bool(exists and expected and actual == expected and not entry.get("parse_error")),
                "parse_error": bool(entry.get("parse_error")),
            }
        )
    return results


def run_operator_command(command: str) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{ROOT / 'src'}{os.pathsep}{env.get('PYTHONPATH', '')}".rstrip(os.pathsep)
    result = subprocess.run(command.split(), cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60, env=env)
    output = result.stdout or ""
    return {
        "command": command,
        "exit_code": result.returncode,
        "contains_missing_marker": "[MISSING]" in output,
        "output_preview": output[:1200],
        "passed": result.returncode == 0 and "[MISSING]" not in output,
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []

    required_bundle_files = []
    for rel_path in REQUIRED_BUNDLE_FILES:
        path = BUNDLE_DIR / rel_path
        exists = path.exists() and path.is_file()
        required_bundle_files.append(
            {
                "path": rel_path,
                "scope": "bundle_directory",
                "exists": exists,
                "sha256": sha256_file(path) if exists else "",
            }
        )
        if not exists:
            errors.append(f"Missing required bundle file: {rel_path}")

    manifest_path = BUNDLE_DIR / "release_handoff_manifest.json"
    manifest_loaded = False
    manifest: dict[str, Any] = {}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest_loaded = True
        except json.JSONDecodeError as exc:
            errors.append(f"Unable to parse release_handoff_manifest.json: {exc}")
    else:
        errors.append("Missing release_handoff_manifest.json")

    checksum_entries = verify_checksum_entries()
    if not checksum_entries:
        errors.append("No checksum entries found in CHECKSUMS.sha256")
    for entry in checksum_entries:
        if entry["parse_error"]:
            errors.append(f"Checksum parse error: {entry['path']}")
        elif not entry["exists"]:
            errors.append(f"Checksum file missing from repository root: {entry['path']}")
        elif not entry["matches"]:
            errors.append(f"Checksum mismatch: {entry['path']}")

    readme_text = read_text_if_present(BUNDLE_DIR / "README.md")
    commands_text = read_text_if_present(BUNDLE_DIR / "OPERATOR_COMMANDS.md")
    truth_text = read_text_if_present(BUNDLE_DIR / "TRUTH_BOUNDARY.md")
    combined_docs = "\n".join([readme_text, commands_text, truth_text])

    documented_commands = []
    for command in DOCUMENTED_COMMANDS:
        documented = command in combined_docs
        documented_commands.append({"command": command, "documented": documented})
        if not documented:
            errors.append(f"Operator command not documented in bundle: {command}")

    operator_smoke_checks = [run_operator_command(command) for command in OPERATOR_COMMANDS]
    for check in operator_smoke_checks:
        if not check["passed"]:
            errors.append(f"Operator replay failed: {check['command']}")

    truth_lower = truth_text.lower()
    truth_boundary_checks = {
        "mentions_local_deterministic": "local deterministic" in truth_lower,
        "mentions_langgraph_openai_policy_gate": "langgraph" in truth_lower and "openai" in truth_lower and "policy-gated" in truth_lower,
        "mentions_not_falsely_claimed": "not falsely claimed" in truth_lower,
    }
    for name, passed in truth_boundary_checks.items():
        if not passed:
            errors.append(f"Truth boundary check failed: {name}")

    audit: dict[str, Any] = {
        "phase": PHASE,
        "app_id": APP_ID,
        "baseline_tag": BASELINE_TAG,
        "baseline_tag_present": git_tag_present(BASELINE_TAG),
        "bundle_directory": str(BUNDLE_DIR.relative_to(ROOT)),
        "handoff_manifest_loaded": manifest_loaded,
        "handoff_manifest_bundle_name": manifest.get("bundle_name", "") if manifest_loaded else "",
        "required_bundle_files": required_bundle_files,
        "checksum_scope": "repository_root",
        "checksum_entries": checksum_entries,
        "operator_command_documentation": documented_commands,
        "operator_smoke_checks": operator_smoke_checks,
        "truth_boundary": "Phase 13K verifies local deterministic handoff replay only. LangGraph/OpenAI execution remains detected and policy-gated, not falsely claimed as active.",
        "truth_boundary_checks": truth_boundary_checks,
        "determinism_policy": {
            "uses_wall_clock_timestamp": False,
            "uses_current_commit_hash": False,
            "reason": "Replay evidence is stable across validation and handoff checks.",
        },
        "errors": errors,
        "passed": not errors and git_tag_present(BASELINE_TAG),
    }
    if not audit["baseline_tag_present"]:
        audit["errors"].append(f"Baseline tag missing: {BASELINE_TAG}")
        audit["passed"] = False

    OUT_FILE.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(audit, indent=2, sort_keys=True))
    return 0 if audit["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
