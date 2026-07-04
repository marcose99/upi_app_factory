#!/usr/bin/env python3
"""
Basic integrity validator for the Governed Agentic Software Factory artifact pack.
This is intentionally dependency-free. It validates required files, JSON syntax,
and manifest hashes. It does not prove project compliance.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent

REQUIRED_FILES = [
    "README.md",
    "00_SYSTEM_PROMPT.md",
    "01_PROJECT_CHARTER_TEMPLATE.md",
    "02_FACTORY_OPERATING_MANUAL.md",
    "03_AGENT_ROLE_PROMPTS.md",
    "04_RISK_TIERS.yaml",
    "05_POLICY_REGISTRY.yaml",
    "06_VALIDATION_GATES.yaml",
    "07_TASK_MANIFEST_SCHEMA.json",
    "08_ARTIFACT_MANIFEST_SCHEMA.json",
    "09_AUDIT_EVENT_SCHEMA.json",
    "10_DEBUG_CASE_SCHEMA.json",
    "11_REGENERATION_GUIDE.md",
    "12_DEBUGGING_PLAYBOOK.md",
    "13_RELEASE_READINESS_CHECKLIST.md",
    "14_SECURITY_AND_RED_TEAM_PLAYBOOK.md",
    "15_OBSERVABILITY_STANDARD.md",
    "16_EVIDENCE_LEDGER_TEMPLATE.csv",
    "17_GOLDEN_REGRESSION_SUITE_TEMPLATE.md",
    "18_HUMAN_APPROVAL_POLICY.md",
    "19_MATURITY_MODEL.md",
    "20_FINAL_REVIEWER_CHECKLIST.md",
    "21_REFERENCE_BASE.md",
    "factory_pack_manifest.json",
]

REQUIRED_TERMS = {
    "00_SYSTEM_PROMPT.md": ["Evidence before assumption", "Policy before action", "Validation before success claims"],
    "02_FACTORY_OPERATING_MANUAL.md": ["Requirement intake", "Validation phase", "Release phase"],
    "05_POLICY_REGISTRY.yaml": ["POL-001-EVIDENCE-FIRST", "POL-007-PROMPT-INJECTION-RESISTANCE", "POL-012-GOLDEN-REGRESSION-MEMORY"],
    "12_DEBUGGING_PLAYBOOK.md": ["Debugging must be forensic", "Search in this order", "Close only when"],
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def main() -> int:
    errors: list[str] = []

    for name in REQUIRED_FILES:
        path = ROOT / name
        if not path.exists():
            errors.append(f"missing required file: {name}")

    for name in ["07_TASK_MANIFEST_SCHEMA.json", "08_ARTIFACT_MANIFEST_SCHEMA.json", "09_AUDIT_EVENT_SCHEMA.json", "10_DEBUG_CASE_SCHEMA.json", "factory_pack_manifest.json"]:
        path = ROOT / name
        if path.exists():
            try:
                json.loads(path.read_text(encoding="utf-8"))
            except Exception as exc:  # noqa: BLE001
                errors.append(f"invalid JSON in {name}: {exc}")

    for name, terms in REQUIRED_TERMS.items():
        path = ROOT / name
        if path.exists():
            text = path.read_text(encoding="utf-8")
            for term in terms:
                if term not in text:
                    errors.append(f"required term missing from {name}: {term}")

    manifest_path = ROOT / "factory_pack_manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for item in manifest.get("files", []):
            name = item.get("path")
            expected = item.get("sha256")
            if not name or not expected:
                errors.append("manifest item missing path or sha256")
                continue
            if name == "factory_pack_manifest.json":
                continue
            path = ROOT / name
            if path.exists():
                actual = sha256(path)
                if actual != expected:
                    errors.append(f"hash mismatch for {name}: expected {expected}, actual {actual}")

    result = {"passed": not errors, "errors": errors}
    print(json.dumps(result, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
