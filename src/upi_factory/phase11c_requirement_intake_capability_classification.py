from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Literal, cast

PHASE = "Phase 11C"
DEFAULT_APP_ID = "upi_dispute_resolution"
GENERATION_MODE = "real_local_primary_payment_application_with_mock_ecosystem"

SupportLevel = Literal[
    "L0_FORBIDDEN",
    "L1_UNSUPPORTED",
    "L2_ANALYSIS_ONLY",
    "L3_CONTRACT_GENERATION",
    "L4_MOCK_ECOSYSTEM_GENERATION",
    "L5_REAL_PRIMARY_APP_PLUS_MOCK_ECOSYSTEM",
]

REQUIRED_FRONT_MATTER: dict[str, str] = {
    "domain": "payments",
    "generation_mode": GENERATION_MODE,
    "primary_application_real": "true",
    "external_ecosystem_mock_only": "true",
    "synthetic_data_only": "true",
    "external_payment_connectivity_allowed": "false",
    "real_payment_processing_allowed": "false",
    "production_claims_allowed": "false",
}

REQUIRED_PREFIXES: tuple[str, ...] = (
    "BR",
    "FR",
    "NFR",
    "GR",
    "MOCK",
    "AC",
)

REQUIRED_ARTIFACTS: tuple[str, ...] = (
    "requirement_intake_manifest.json",
    "normalized_requirements.json",
    "payment_capability_classification_report.json",
    "support_level_decision.json",
    "requirement_traceability_matrix.md",
    "requirement_gap_report.md",
    "llm_expense_tracking_policy.md",
    "generation_contract.json",
    "phase11c_readiness_report.json",
)

FORBIDDEN_UNSAFE_CLAIMS: tuple[str, ...] = (
    "production ready",
    "production compliant",
    "rbi certified",
    "npci certified",
    "pci certified",
    "approved for live payment use",
    "connects to real npci",
    "connects to real rbi",
    "connects to real bank",
    "processes real payments",
    "uses real customer data",
)

REQUIRED_BOUNDARY_FLAGS: tuple[str, ...] = (
    "primary_application_real",
    "external_ecosystem_mock_only",
    "synthetic_data_only",
    "external_payment_connectivity_allowed",
    "real_payment_processing_allowed",
    "production_claims_allowed",
)

CAPABILITY_REGISTRY: dict[str, dict[str, Any]] = {
    "upi_dispute_resolution": {
        "rail": "upi",
        "application_archetype": "case_management_app",
        "support_level": "L5_REAL_PRIMARY_APP_PLUS_MOCK_ECOSYSTEM",
        "keywords": [
            "upi",
            "dispute",
            "case",
            "resolution",
            "state transition",
            "audit",
        ],
        "primary_components": [
            "dispute_api",
            "dispute_domain_model",
            "state_transition_engine",
            "audit_event_store",
        ],
        "mock_ecosystem_components": [
            "simulated_transaction_registry",
            "simulated_bank_service",
            "simulated_notification_service",
        ],
    },
    "upi_failed_transaction": {
        "rail": "upi",
        "application_archetype": "transaction_workflow_app",
        "support_level": "L4_MOCK_ECOSYSTEM_GENERATION",
        "keywords": ["upi", "failed transaction", "pending", "reversal"],
        "primary_components": [
            "transaction_status_api",
            "failure_reason_classifier",
            "reversal_workflow",
        ],
        "mock_ecosystem_components": [
            "simulated_payment_rail",
            "simulated_bank_service",
        ],
    },
    "refund_orchestration": {
        "rail": "generic_payment",
        "application_archetype": "workflow_orchestration_app",
        "support_level": "L3_CONTRACT_GENERATION",
        "keywords": ["refund", "refund request", "refund workflow"],
        "primary_components": ["refund_api", "refund_workflow_contract"],
        "mock_ecosystem_components": ["simulated_ledger", "simulated_notification"],
    },
    "card_chargeback_workflow": {
        "rail": "cards",
        "application_archetype": "case_management_app",
        "support_level": "L3_CONTRACT_GENERATION",
        "keywords": ["card", "chargeback", "issuer", "acquirer"],
        "primary_components": ["chargeback_case_api", "evidence_contracts"],
        "mock_ecosystem_components": ["simulated_issuer", "simulated_acquirer"],
    },
    "payment_reconciliation": {
        "rail": "generic_payment",
        "application_archetype": "reconciliation_app",
        "support_level": "L2_ANALYSIS_ONLY",
        "keywords": ["reconciliation", "matching", "break", "ledger"],
        "primary_components": ["reconciliation_analysis_contract"],
        "mock_ecosystem_components": ["simulated_ledger_source"],
    },
    "settlement_exception": {
        "rail": "generic_payment",
        "application_archetype": "exception_management_app",
        "support_level": "L2_ANALYSIS_ONLY",
        "keywords": ["settlement", "exception", "batch"],
        "primary_components": ["settlement_exception_contract"],
        "mock_ecosystem_components": ["simulated_settlement_source"],
    },
    "fraud_case_management": {
        "rail": "generic_payment",
        "application_archetype": "case_management_app",
        "support_level": "L2_ANALYSIS_ONLY",
        "keywords": ["fraud", "risk", "case review"],
        "primary_components": ["fraud_case_contract"],
        "mock_ecosystem_components": ["simulated_risk_score_service"],
    },
    "notification_orchestration": {
        "rail": "generic_payment",
        "application_archetype": "notification_app",
        "support_level": "L4_MOCK_ECOSYSTEM_GENERATION",
        "keywords": ["notification", "sms", "email", "push"],
        "primary_components": ["notification_orchestration_api"],
        "mock_ecosystem_components": ["simulated_notification_provider"],
    },
    "audit_evidence_service": {
        "rail": "generic_payment",
        "application_archetype": "audit_evidence_app",
        "support_level": "L5_REAL_PRIMARY_APP_PLUS_MOCK_ECOSYSTEM",
        "keywords": ["audit", "evidence", "traceability", "correlation"],
        "primary_components": ["audit_evidence_api", "traceability_store"],
        "mock_ecosystem_components": ["simulated_evidence_sink"],
    },
}


def _write_text(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")
    return path


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _json_loads_dict(text: str) -> dict[str, Any]:
    loaded = json.loads(text)
    if not isinstance(loaded, dict):
        raise ValueError("Expected a JSON object.")
    return cast(dict[str, Any], loaded)


def parse_front_matter(markdown_text: str) -> tuple[dict[str, str], str]:
    if not markdown_text.startswith("---\n"):
        return {}, markdown_text

    closing = markdown_text.find("\n---\n", 4)
    if closing == -1:
        return {}, markdown_text

    raw_front_matter = markdown_text[4:closing]
    body = markdown_text[closing + 5 :]
    parsed: dict[str, str] = {}

    for raw_line in raw_front_matter.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, raw_value = line.split(":", 1)
        parsed[key.strip()] = raw_value.strip().strip('"').strip("'").lower()

    return parsed, body


def extract_requirement_ids(markdown_text: str) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {prefix: [] for prefix in REQUIRED_PREFIXES}
    pattern = re.compile(r"^([A-Z]+)-(\d{3})\s*:", re.MULTILINE)

    for match in pattern.finditer(markdown_text):
        prefix = match.group(1)
        if prefix in found:
            found[prefix].append(f"{prefix}-{match.group(2)}")

    return found


def find_forbidden_claims(text: str) -> list[str]:
    lowered = text.lower()
    return [claim for claim in FORBIDDEN_UNSAFE_CLAIMS if claim in lowered]


def validate_requirement_document(requirement_doc: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    if not requirement_doc.exists():
        return {
            "passed": False,
            "errors": [f"Requirement document not found: {requirement_doc}"],
            "warnings": [],
            "front_matter": {},
            "requirement_ids": {},
            "forbidden_claims": [],
        }

    text = _read_text(requirement_doc)
    front_matter, _body = parse_front_matter(text)

    if not front_matter:
        errors.append("Requirement document must contain YAML-style front matter.")

    for key, expected in REQUIRED_FRONT_MATTER.items():
        actual = front_matter.get(key)
        if actual != expected:
            errors.append(
                f"Front matter {key!r} must be {expected!r}; found {actual!r}."
            )

    requirement_ids = extract_requirement_ids(text)
    for prefix in REQUIRED_PREFIXES:
        if not requirement_ids[prefix]:
            errors.append(f"Missing at least one {prefix}-nnn requirement ID.")

    forbidden_claims = find_forbidden_claims(text)
    for claim in forbidden_claims:
        errors.append(f"Unsafe requirement wording found: {claim}")

    if not errors:
        warnings.append(
            "Requirement document is safe for payment capability classification."
        )

    return {
        "passed": not errors,
        "errors": errors,
        "warnings": warnings,
        "front_matter": front_matter,
        "requirement_ids": requirement_ids,
        "forbidden_claims": forbidden_claims,
    }


def classify_payment_capabilities(markdown_text: str) -> dict[str, Any]:
    lowered = markdown_text.lower()
    detected: list[dict[str, Any]] = []

    for capability_id, capability in CAPABILITY_REGISTRY.items():
        keywords = cast(list[str], capability["keywords"])
        matched_keywords = [keyword for keyword in keywords if keyword in lowered]
        if matched_keywords:
            detected.append(
                {
                    "capability_id": capability_id,
                    "rail": capability["rail"],
                    "application_archetype": capability[
                        "application_archetype"
                    ],
                    "support_level": capability["support_level"],
                    "matched_keywords": matched_keywords,
                    "primary_components": capability["primary_components"],
                    "mock_ecosystem_components": capability[
                        "mock_ecosystem_components"
                    ],
                }
            )

    detected.sort(
        key=lambda item: (
            int(cast(str, item["support_level"])[1]),
            len(cast(list[str], item["matched_keywords"])),
        ),
        reverse=True,
    )

    return {
        "detected_capabilities": detected,
        "capability_count": len(detected),
        "primary_capability": detected[0] if detected else None,
    }


def decide_support_level(
    requirement_validation: dict[str, Any],
    classification: dict[str, Any],
) -> dict[str, Any]:
    if not requirement_validation["passed"]:
        return {
            "decision": "FORBIDDEN_OR_INVALID",
            "support_level": "L0_FORBIDDEN",
            "generation_contract_allowed": False,
            "reason": "Requirement document failed intake validation.",
        }

    detected = cast(list[dict[str, Any]], classification["detected_capabilities"])
    if not detected:
        return {
            "decision": "UNSUPPORTED",
            "support_level": "L1_UNSUPPORTED",
            "generation_contract_allowed": False,
            "reason": "No registered payment capability matched the requirement.",
        }

    primary = detected[0]
    primary_level = cast(SupportLevel, primary["support_level"])
    allowed = primary_level in (
        "L3_CONTRACT_GENERATION",
        "L4_MOCK_ECOSYSTEM_GENERATION",
        "L5_REAL_PRIMARY_APP_PLUS_MOCK_ECOSYSTEM",
    )

    return {
        "decision": "SUPPORTED" if allowed else "PARTIALLY_SUPPORTED",
        "support_level": primary_level,
        "generation_contract_allowed": allowed,
        "reason": (
            "Requirement matched a registered payment capability and respects "
            "the real-primary-app with simulated-ecosystem boundary."
        ),
    }


def build_generation_contract(
    requirement_doc: Path,
    requirement_validation: dict[str, Any],
    classification: dict[str, Any],
    support_decision: dict[str, Any],
) -> dict[str, Any]:
    front_matter = cast(dict[str, str], requirement_validation["front_matter"])
    detected = cast(list[dict[str, Any]], classification["detected_capabilities"])
    primary = detected[0] if detected else None

    contract: dict[str, Any] = {
        "contract_generated": bool(support_decision["generation_contract_allowed"]),
        "phase": PHASE,
        "requirement_document": str(requirement_doc),
        "requirement_id": front_matter.get("requirement_id", ""),
        "app_id": front_matter.get("app_id", DEFAULT_APP_ID),
        "domain": "payments",
        "generation_mode": GENERATION_MODE,
        "primary_application_real": True,
        "external_ecosystem_mock_only": True,
        "synthetic_data_only": True,
        "external_payment_connectivity_allowed": False,
        "real_payment_processing_allowed": False,
        "production_claims_allowed": False,
        "support_decision": support_decision,
        "selected_capability": primary,
        "detected_capabilities": detected,
        "quality_gates": ["ruff", "mypy", "pytest", "phase11c_validation"],
        "llm_expense_tracking_required": True,
        "llm_expense_tracking": {
            "pricing_config_required": True,
            "pricing_config_source": "project-supplied build-time pricing config",
            "per_call_ledger_required": True,
            "per_call_required_fields": [
                "call_id",
                "agent_name",
                "model",
                "input_tokens",
                "output_tokens",
                "cached_input_tokens",
                "reasoning_tokens",
                "unit_prices_used",
                "calculated_cost",
                "currency",
                "timestamp_utc",
                "purpose",
            ],
            "final_summary_required": True,
            "final_summary_artifacts": [
                "llm_call_expense_ledger.jsonl",
                "llm_expense_summary.json",
                "llm_expense_report.md",
            ],
            "final_summary_must_be_last_llm_dependent_artifact": True,
            "no_llm_calls_after_final_summary": True,
        },
    }

    if primary:
        contract["services_to_generate"] = primary["primary_components"]
        contract["mock_ecosystem_to_generate"] = primary[
            "mock_ecosystem_components"
        ]
        contract["application_archetype"] = primary["application_archetype"]
    else:
        contract["services_to_generate"] = []
        contract["mock_ecosystem_to_generate"] = []
        contract["application_archetype"] = ""

    return contract


def _traceability_matrix(requirement_ids: dict[str, list[str]]) -> str:
    lines = [
        "# Requirement Traceability Matrix",
        "",
        "| Requirement ID | Type | Intake Status | Downstream Mapping |",
        "|---|---|---|---|",
    ]
    for prefix in REQUIRED_PREFIXES:
        for requirement_id in requirement_ids[prefix]:
            lines.append(
                "| "
                f"{requirement_id} | {prefix} | accepted | "
                "mapped into generation contract |"
            )
    return "\n".join(lines)


def _gap_report(
    requirement_validation: dict[str, Any],
    classification: dict[str, Any],
    support_decision: dict[str, Any],
) -> str:
    lines = [
        "# Requirement Gap Report",
        "",
        f"Decision: {support_decision['decision']}",
        f"Support level: {support_decision['support_level']}",
        "",
    ]

    errors = cast(list[str], requirement_validation["errors"])
    detected = cast(list[dict[str, Any]], classification["detected_capabilities"])

    if errors:
        lines.append("## Intake Errors")
        for error in errors:
            lines.append(f"- {error}")
    elif not detected:
        lines.append("## Capability Gaps")
        lines.append("- No registered payment capability matched the requirement.")
    else:
        lines.append("## Gaps")
        lines.append("- No blocking gaps detected for the selected support level.")

    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- Primary payment application: real local software.",
            "- External ecosystem applications: simulated.",
            "- External connectivity: fail closed.",
            "- Data: synthetic only.",
        ]
    )
    return "\n".join(lines)


def generate_phase11c_artifacts(
    output_dir: Path,
    requirement_doc: Path,
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    requirement_text = _read_text(requirement_doc)
    requirement_validation = validate_requirement_document(requirement_doc)
    classification = classify_payment_capabilities(requirement_text)
    support_decision = decide_support_level(requirement_validation, classification)
    generation_contract = build_generation_contract(
        requirement_doc,
        requirement_validation,
        classification,
        support_decision,
    )

    requirement_ids = cast(dict[str, list[str]], requirement_validation[
        "requirement_ids"
    ])

    generated = [
        _write_json(
            output_dir / "requirement_intake_manifest.json",
            {
                "phase": PHASE,
                "requirement_document": str(requirement_doc),
                "passed": requirement_validation["passed"],
                "front_matter": requirement_validation["front_matter"],
                "requirement_id_counts": {
                    prefix: len(requirement_ids[prefix])
                    for prefix in REQUIRED_PREFIXES
                },
                "boundary_flags_checked": list(REQUIRED_BOUNDARY_FLAGS),
            },
        ),
        _write_json(
            output_dir / "normalized_requirements.json",
            {
                "phase": PHASE,
                "requirement_ids": requirement_ids,
                "front_matter": requirement_validation["front_matter"],
                "open_question_ids": re.findall(r"^Q-(\d{3})\s*:", requirement_text, re.MULTILINE),
            },
        ),
        _write_json(
            output_dir / "payment_capability_classification_report.json",
            classification,
        ),
        _write_json(output_dir / "support_level_decision.json", support_decision),
        _write_text(
            output_dir / "requirement_traceability_matrix.md",
            _traceability_matrix(requirement_ids),
        ),
        _write_text(
            output_dir / "requirement_gap_report.md",
            _gap_report(requirement_validation, classification, support_decision),
        ),
        _write_text(
            output_dir / "llm_expense_tracking_policy.md",
            """
# LLM Expense Tracking Policy

The application build must record every LLM call in a per-call ledger.

Required per-call fields:
- call_id
- agent_name
- model
- input_tokens
- output_tokens
- cached_input_tokens
- reasoning_tokens
- unit_prices_used
- calculated_cost
- currency
- timestamp_utc
- purpose

The build must use a project-supplied pricing configuration captured at
the start of the run. The factory must not hard-code changing provider
prices into prompts or generated source code.

At the end of all application-build LLM calls, the factory must produce:
- llm_call_expense_ledger.jsonl
- llm_expense_summary.json
- llm_expense_report.md

The consolidated LLM expense summary must be the final LLM-dependent
artifact. No additional LLM calls are permitted after the final expense
summary is emitted.
""",
        ),
        _write_json(output_dir / "generation_contract.json", generation_contract),
    ]

    readiness_report = validate_phase11c_artifacts(output_dir)
    generated.append(
        _write_json(output_dir / "phase11c_readiness_report.json", readiness_report)
    )
    return generated


def validate_phase11c_artifacts(
    output_dir: Path,
    project_root: Path | None = None,
) -> dict[str, Any]:
    del project_root

    errors: list[str] = []
    warnings: list[str] = []

    for artifact_name in REQUIRED_ARTIFACTS:
        if artifact_name == "phase11c_readiness_report.json":
            continue
        if not (output_dir / artifact_name).exists():
            errors.append(f"Missing required artifact: {artifact_name}")

    json_artifacts = [
        "requirement_intake_manifest.json",
        "normalized_requirements.json",
        "payment_capability_classification_report.json",
        "support_level_decision.json",
        "generation_contract.json",
    ]
    loaded_artifacts: dict[str, dict[str, Any]] = {}
    for artifact_name in json_artifacts:
        path = output_dir / artifact_name
        if not path.exists():
            continue
        try:
            loaded_artifacts[artifact_name] = _json_loads_dict(_read_text(path))
        except ValueError as exc:
            errors.append(f"Invalid JSON object in {artifact_name}: {exc}")

    contract = loaded_artifacts.get("generation_contract.json", {})
    expected_contract_values: dict[str, Any] = {
        "generation_mode": GENERATION_MODE,
        "primary_application_real": True,
        "external_ecosystem_mock_only": True,
        "synthetic_data_only": True,
        "external_payment_connectivity_allowed": False,
        "real_payment_processing_allowed": False,
        "production_claims_allowed": False,
        "llm_expense_tracking_required": True,
    }
    for key, expected in expected_contract_values.items():
        if contract and contract.get(key) != expected:
            errors.append(
                f"Generation contract {key!r} must be {expected!r}; "
                f"found {contract.get(key)!r}."
            )

    support_decision = loaded_artifacts.get("support_level_decision.json", {})
    if support_decision.get("support_level") == "L0_FORBIDDEN":
        errors.append("Support decision is forbidden.")

    combined_text_parts: list[str] = []
    for artifact_name in REQUIRED_ARTIFACTS:
        path = output_dir / artifact_name
        if path.exists() and artifact_name != "phase11c_readiness_report.json":
            combined_text_parts.append(_read_text(path))
    forbidden_claims = find_forbidden_claims("\n".join(combined_text_parts))
    for claim in forbidden_claims:
        errors.append(f"Unsafe claim found in Phase 11C artifacts: {claim}")

    if not errors:
        warnings.append(
            "Phase 11C is ready: requirement intake, capability "
            "classification, support decision, gap report, and generation "
            "contract were produced."
        )

    return {
        "artifact": "phase11c_readiness_report.json",
        "phase": PHASE,
        "passed": not errors,
        "errors": errors,
        "warnings": warnings,
        "checked_artifacts": list(REQUIRED_ARTIFACTS),
        "generation_mode": GENERATION_MODE,
    }
