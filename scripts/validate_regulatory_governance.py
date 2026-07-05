#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = PROJECT_ROOT / "docs" / "software_and_payment_regulatory_governance.md"
REGISTRY_PATH = PROJECT_ROOT / "factory_governance" / "regulatory" / "regulatory_source_registry.json"
MATRIX_PATH = PROJECT_ROOT / "factory_governance" / "regulatory" / "regulatory_applicability_matrix.json"
PROMPTS_DIR = PROJECT_ROOT / "factory_governance" / "agent_prompts" / "prompts"

REQUIRED_DOC_TERMS = [
    "software-engineering",
    "payment regulatory",
    "regulatory alignment, not certification",
    "mocked",
    "NIST SSDF",
    "OWASP",
    "SLSA",
    "OpenTelemetry",
    "RBI",
    "NPCI",
    "PCI DSS",
    "DPDP",
    "MISSING_OFFICIAL_SOURCE",
    "MOCK_BOUNDARY",
    "SYNTHETIC_DATA",
]

REQUIRED_PROMPT_TERMS = [
    "Software-engineering and payment regulatory governance",
    "software engineering regulatory alignment",
    "payment regulatory alignment",
    "regulatory alignment, not certification",
    "NIST SSDF",
    "OWASP",
    "SLSA",
    "OpenTelemetry",
    "RBI",
    "NPCI",
    "PCI DSS",
    "DPDP",
    "mocked ecosystem",
    "highly modular",
    "industry standard",
    "software life cycle",
    "near-certifiable",
    "MISSING_OFFICIAL_SOURCE",
    "MOCK_BOUNDARY",
    "SYNTHETIC_DATA",
]

REQUIRED_SOURCE_IDS = {
    "SER-NIST-SSDF",
    "SER-OWASP-LLM",
    "SER-SLSA-PROVENANCE",
    "SER-OPENTELEMETRY",
    "PAY-RBI-DPSC-2021",
    "PAY-RBI-ODR-2020",
    "PAY-RBI-CUSTOMER-LIABILITY-2017",
    "PAY-NPCI-UPI-CIRCULARS",
    "PAY-PCI-DSS-401",
    "DATA-DPDP-ACT-2023",
}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate() -> list[str]:
    errors: list[str] = []

    for path in [DOC_PATH, REGISTRY_PATH, MATRIX_PATH]:
        if not path.exists():
            errors.append(f"Missing required file: {path.relative_to(PROJECT_ROOT)}")
            return errors

    doc_text = DOC_PATH.read_text(encoding="utf-8")
    for term in REQUIRED_DOC_TERMS:
        if term not in doc_text:
            errors.append(f"Regulatory governance document is missing required term: {term}")

    registry = _load_json(REGISTRY_PATH)
    matrix = _load_json(MATRIX_PATH)

    if registry.get("schema_version") != "factory.regulatory_source_registry.v1":
        errors.append("Regulatory source registry has unexpected schema_version")

    if matrix.get("schema_version") != "factory.regulatory_applicability_matrix.v1":
        errors.append("Regulatory applicability matrix has unexpected schema_version")

    collected_ids: set[str] = set()
    for section in [
        "software_engineering_references",
        "payment_regulatory_references",
        "privacy_data_references",
    ]:
        for item in registry.get(section, []):
            source_id = item.get("id")
            if source_id:
                collected_ids.add(source_id)
            for required_field in ["id", "name", "source_owner", "source_type", "url", "applicability", "current_use"]:
                if not item.get(required_field):
                    errors.append(f"{source_id or section} is missing field: {required_field}")

    missing_sources = sorted(REQUIRED_SOURCE_IDS - collected_ids)
    if missing_sources:
        errors.append(f"Regulatory source registry is missing required source IDs: {missing_sources}")

    matrix_ids = {entry.get("source_id") for entry in matrix.get("entries", [])}
    missing_matrix_entries = sorted(REQUIRED_SOURCE_IDS - matrix_ids)
    if missing_matrix_entries:
        errors.append(f"Regulatory applicability matrix is missing source IDs: {missing_matrix_entries}")

    if not PROMPTS_DIR.exists():
        errors.append(f"Missing prompt directory: {PROMPTS_DIR.relative_to(PROJECT_ROOT)}")
        return errors

    prompt_files = sorted(PROMPTS_DIR.glob("*.md"))
    if not prompt_files:
        errors.append("No governed agent prompts found")
        return errors

    for prompt_path in prompt_files:
        text = prompt_path.read_text(encoding="utf-8")
        for term in REQUIRED_PROMPT_TERMS:
            if term not in text:
                errors.append(f"{prompt_path.name} is missing required regulatory term: {term}")

    return errors


def main() -> int:
    errors = validate()
    passed = not errors
    print(json.dumps({"errors": errors, "passed": passed}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
