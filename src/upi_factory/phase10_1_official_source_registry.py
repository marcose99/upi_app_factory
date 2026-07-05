"""Phase 10.1 official-source evidence registry.

This module creates deterministic source-governance artifacts for the mock
UPI dispute-resolution factory.

Important boundary:
- It records official-source references and source-backed engineering claims.
- It does not fetch live websites at runtime.
- It does not provide legal advice.
- It does not claim RBI, NPCI, bank, or production certification.
- Dynamic values such as current UPI volume, vendor pricing, bank cost per
  dispute, and live ROI must remain source gaps unless supplied and verified.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REQUIRED_ARTIFACTS: tuple[str, ...] = (
    "official_source_registry.json",
    "official_source_evidence_pack.md",
    "regulatory_economics_source_gap_report.json",
    "source_freshness_policy.md",
    "source_usage_policy.md",
    "source_to_requirement_traceability.json",
    "official_source_validation_report.json",
)

REQUIRED_SOURCE_IDS: tuple[str, ...] = (
    "RBI_ODR_DIGITAL_PAYMENTS_2020",
    "RBI_FAILED_TRANSACTION_TAT_2019",
    "RBI_LIMITED_LIABILITY_2017",
    "NPCI_UPI_PRODUCT_STATISTICS",
    "NPCI_COMPLAINT_STATUS",
    "NPCI_UPI_PRODUCT_PAGE",
)

REQUIRED_LABELS: tuple[str, ...] = (
    "SOURCE_BACKED_REFERENCE",
    "OFFICIAL_SOURCE_REFERENCE",
    "MISSING_OFFICIAL_SOURCE",
    "SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL",
    "MOCK_BOUNDARY",
    "SYNTHETIC_DATA",
    "USER_PROVIDED_VALUE",
)

FORBIDDEN_CLAIMS: tuple[str, ...] = (
    "RBI certified",
    "NPCI certified",
    "officially certified",
    "guaranteed compliant",
    "100% compliant",
    "production compliant",
    "legal advice",
    "real UPI integration",
    "live NPCI integration",
    "live bank integration",
)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _write_markdown(path: Path, text: str) -> None:
    path.write_text(text.strip() + "\n", encoding="utf-8")


def _source_registry(app_id: str) -> dict[str, Any]:
    """Return the deterministic official-source registry."""

    return {
        "artifact": "official_source_registry.json",
        "app_id": app_id,
        "phase": "Phase 10.1",
        "purpose": (
            "Convert Phase 10 reference candidates into governed source entries "
            "that future requirements, design, economics, and regulatory-alignment "
            "prompts can use without inventing facts."
        ),
        "runtime_network_access": False,
        "source_governance_boundary": {
            "not_legal_advice": True,
            "not_compliance_certification": True,
            "not_rbi_npci_approval": True,
            "mock_safe": True,
            "no_live_payment_network_calls": True,
        },
        "required_labels": list(REQUIRED_LABELS),
        "sources": [
            {
                "source_id": "RBI_ODR_DIGITAL_PAYMENTS_2020",
                "authority": "Reserve Bank of India",
                "title": "Online Dispute Resolution (ODR) System for Digital Payments",
                "url": (
                    "https://www.rbi.org.in/commonman/english/scripts/"
                    "Notification.aspx?Id=3194"
                ),
                "publication_date": "2020-08-06",
                "document_reference": "DPSS.CO.PD No.116/02.12.004/2020-21",
                "source_status": "OFFICIAL_SOURCE_REFERENCE",
                "freshness_class": "stable_circular_verify_before_release",
                "allowed_usage": [
                    "ODR concept modelling",
                    "failed-transaction dispute scope",
                    "rule-based system-driven design inspiration",
                    "customer lodging and tracking design requirements",
                    "data-minimisation and confidentiality design prompts",
                ],
                "prohibited_usage": [
                    "claiming actual ODR implementation",
                    "claiming RBI approval or certification",
                    "claiming production compliance",
                    "using as legal advice",
                ],
                "extracted_claims": [
                    {
                        "claim_id": "SRC-ODR-001",
                        "claim_text": (
                            "RBI described ODR for digital-payment customer disputes "
                            "as system-driven and rule-based, with zero or minimal "
                            "manual intervention."
                        ),
                        "claim_usage": "architecture_and_workflow_prompting",
                        "maps_to_requirement_ids": ["RQ-REG-001", "RQ-GOV-001"],
                        "honesty_labels": [
                            "SOURCE_BACKED_REFERENCE",
                            "OFFICIAL_SOURCE_REFERENCE",
                        ],
                    },
                    {
                        "claim_id": "SRC-ODR-002",
                        "claim_text": (
                            "The initial ODR scope covered disputes and grievances "
                            "related to failed transactions."
                        ),
                        "claim_usage": "domain_scope_prompting",
                        "maps_to_requirement_ids": ["RQ-FUN-002", "RQ-REG-001"],
                        "honesty_labels": [
                            "SOURCE_BACKED_REFERENCE",
                            "OFFICIAL_SOURCE_REFERENCE",
                        ],
                    },
                    {
                        "claim_id": "SRC-ODR-003",
                        "claim_text": (
                            "The ODR design expectation includes simple lodging, "
                            "necessary minimum details, confidentiality, unique "
                            "reference number, and tracking."
                        ),
                        "claim_usage": "application_requirement_prompting",
                        "maps_to_requirement_ids": [
                            "RQ-FUN-001",
                            "RQ-FUN-003",
                            "RQ-REG-001",
                        ],
                        "honesty_labels": [
                            "SOURCE_BACKED_REFERENCE",
                            "OFFICIAL_SOURCE_REFERENCE",
                        ],
                    },
                ],
            },
            {
                "source_id": "RBI_FAILED_TRANSACTION_TAT_2019",
                "authority": "Reserve Bank of India",
                "title": (
                    "Harmonisation of Turn Around Time (TAT) and customer "
                    "compensation for failed transactions using authorised "
                    "Payment Systems"
                ),
                "url": (
                    "https://www.rbi.org.in/commonman/English/scripts/"
                    "Notification.aspx?Id=3074"
                ),
                "publication_date": "2019-09-20",
                "document_reference": "DPSS.CO.PD No.629/02.01.014/2019-20",
                "source_status": "OFFICIAL_SOURCE_REFERENCE",
                "freshness_class": "stable_circular_verify_before_release",
                "allowed_usage": [
                    "failed-transaction definition",
                    "UPI failed-transaction scenario modelling",
                    "TAT and compensation awareness",
                    "economics exposure modelling with source-backed labels",
                ],
                "prohibited_usage": [
                    "hard-coding live legal obligations without review",
                    "claiming automated compensation is production-ready",
                    "claiming bank-specific policy coverage",
                ],
                "extracted_claims": [
                    {
                        "claim_id": "SRC-TAT-001",
                        "claim_text": (
                            "RBI defined failed transactions to include cases not "
                            "fully completed for reasons not attributable to the "
                            "customer, including communication failure, timeout, "
                            "non-credit to beneficiary, or delayed reversal."
                        ),
                        "claim_usage": "domain_and_policy_prompting",
                        "maps_to_requirement_ids": ["RQ-FUN-002", "RQ-REG-001"],
                        "honesty_labels": [
                            "SOURCE_BACKED_REFERENCE",
                            "OFFICIAL_SOURCE_REFERENCE",
                        ],
                    },
                    {
                        "claim_id": "SRC-TAT-002",
                        "claim_text": (
                            "For UPI transfer of funds where the account is debited "
                            "but the beneficiary account is not credited, the source "
                            "lists auto-reversal by the beneficiary bank latest on "
                            "T + 1 day and compensation if delay is beyond T + 1 day."
                        ),
                        "claim_usage": "source_backed_scenario_prompting",
                        "maps_to_requirement_ids": [
                            "RQ-FUN-002",
                            "RQ-REG-001",
                            "RQ-ECO-002",
                        ],
                        "honesty_labels": [
                            "SOURCE_BACKED_REFERENCE",
                            "OFFICIAL_SOURCE_REFERENCE",
                        ],
                    },
                    {
                        "claim_id": "SRC-TAT-003",
                        "claim_text": (
                            "For UPI merchant payment where the account is debited "
                            "but transaction confirmation is not received at the "
                            "merchant location, the source lists auto-reversal "
                            "within T + 5 days and compensation if delay is beyond "
                            "T + 5 days."
                        ),
                        "claim_usage": "source_backed_scenario_prompting",
                        "maps_to_requirement_ids": [
                            "RQ-FUN-002",
                            "RQ-REG-001",
                            "RQ-ECO-002",
                        ],
                        "honesty_labels": [
                            "SOURCE_BACKED_REFERENCE",
                            "OFFICIAL_SOURCE_REFERENCE",
                        ],
                    },
                ],
            },
            {
                "source_id": "RBI_LIMITED_LIABILITY_2017",
                "authority": "Reserve Bank of India",
                "title": (
                    "Customer Protection - Limiting Liability of Customers in "
                    "Unauthorised Electronic Banking Transactions"
                ),
                "url": (
                    "https://www.rbi.org.in/commonman/english/scripts/"
                    "Notification.aspx?Id=2336"
                ),
                "publication_date": "2017-07-06",
                "document_reference": "DBR.No.Leg.BC.78/09.07.005/2017-18",
                "source_status": "OFFICIAL_SOURCE_REFERENCE",
                "freshness_class": "stable_circular_verify_before_release",
                "allowed_usage": [
                    "unauthorised-transaction escalation awareness",
                    "customer reporting and acknowledgement design prompts",
                    "customer-liability source-gap handling",
                    "security and fraud-control quality prompts",
                ],
                "prohibited_usage": [
                    "treating fraud liability as same as failed UPI dispute",
                    "automating legal liability decisions",
                    "claiming bank-specific board-policy coverage",
                ],
                "extracted_claims": [
                    {
                        "claim_id": "SRC-LIAB-001",
                        "claim_text": (
                            "The source discusses customer notification timing, "
                            "bank reporting channels, acknowledgement, and recording "
                            "time/date of customer response for unauthorised "
                            "electronic transactions."
                        ),
                        "claim_usage": "security_and_escalation_prompting",
                        "maps_to_requirement_ids": [
                            "RQ-FUN-003",
                            "RQ-GOV-001",
                            "RQ-REG-001",
                        ],
                        "honesty_labels": [
                            "SOURCE_BACKED_REFERENCE",
                            "OFFICIAL_SOURCE_REFERENCE",
                        ],
                    },
                    {
                        "claim_id": "SRC-LIAB-002",
                        "claim_text": (
                            "The source states zero liability can arise in specified "
                            "third-party breach circumstances when the customer "
                            "notifies the bank within three working days."
                        ),
                        "claim_usage": "source_backed_escalation_context",
                        "maps_to_requirement_ids": [
                            "RQ-REG-001",
                            "RQ-ECO-002",
                        ],
                        "honesty_labels": [
                            "SOURCE_BACKED_REFERENCE",
                            "OFFICIAL_SOURCE_REFERENCE",
                        ],
                    },
                    {
                        "claim_id": "SRC-LIAB-003",
                        "claim_text": (
                            "The source states banks should resolve complaints and "
                            "establish customer liability within timelines specified "
                            "by board-approved policy, not exceeding 90 days."
                        ),
                        "claim_usage": "source_backed_escalation_context",
                        "maps_to_requirement_ids": [
                            "RQ-REG-001",
                            "RQ-ECO-002",
                        ],
                        "honesty_labels": [
                            "SOURCE_BACKED_REFERENCE",
                            "OFFICIAL_SOURCE_REFERENCE",
                        ],
                    },
                ],
            },
            {
                "source_id": "NPCI_UPI_PRODUCT_STATISTICS",
                "authority": "National Payments Corporation of India",
                "title": "Unified Payments Interface (UPI) Product Statistics",
                "url": "https://www.npci.org.in/product/upi/product-statistics",
                "publication_date": "DYNAMIC_WEB_PAGE",
                "document_reference": "NPCI UPI statistics page",
                "source_status": "OFFICIAL_DYNAMIC_SOURCE_REFERENCE",
                "freshness_class": "dynamic_verify_on_every_release",
                "allowed_usage": [
                    "current UPI volume/value source candidate",
                    "capacity planning input when manually captured",
                    "economics sensitivity analysis when date-stamped",
                ],
                "prohibited_usage": [
                    "embedding current transaction volume without capture date",
                    "claiming live values from stale copied data",
                    "using dynamic values without USER_PROVIDED_VALUE or source date",
                ],
                "extracted_claims": [
                    {
                        "claim_id": "SRC-NPCI-STATS-001",
                        "claim_text": (
                            "NPCI provides an official UPI product statistics page. "
                            "Current volume and value figures are dynamic and must "
                            "be captured with date, source URL, and review status."
                        ),
                        "claim_usage": "economics_capacity_source_candidate",
                        "maps_to_requirement_ids": ["RQ-ECO-001", "RQ-ECO-002"],
                        "honesty_labels": [
                            "OFFICIAL_SOURCE_REFERENCE",
                            "MISSING_OFFICIAL_SOURCE",
                        ],
                    },
                ],
            },
            {
                "source_id": "NPCI_COMPLAINT_STATUS",
                "authority": "National Payments Corporation of India",
                "title": "User Complaint Status",
                "url": "https://www.npci.org.in/complaint-status",
                "publication_date": "DYNAMIC_WEB_PAGE",
                "document_reference": "NPCI complaint-status page",
                "source_status": "OFFICIAL_DYNAMIC_SOURCE_REFERENCE",
                "freshness_class": "dynamic_verify_before_demo_or_release",
                "allowed_usage": [
                    "complaint-status and tracking concept reference",
                    "mock customer status-tracking design inspiration",
                ],
                "prohibited_usage": [
                    "calling the live NPCI complaint-status page",
                    "submitting real complaint details",
                    "claiming factory integration with NPCI",
                ],
                "extracted_claims": [
                    {
                        "claim_id": "SRC-NPCI-COMPLAINT-001",
                        "claim_text": (
                            "NPCI exposes a public complaint-status page, but the "
                            "factory must model this only as a mock boundary."
                        ),
                        "claim_usage": "mock_boundary_prompting",
                        "maps_to_requirement_ids": ["RQ-FUN-004", "RQ-REG-001"],
                        "honesty_labels": [
                            "OFFICIAL_SOURCE_REFERENCE",
                            "MOCK_BOUNDARY",
                        ],
                    },
                ],
            },
            {
                "source_id": "NPCI_UPI_PRODUCT_PAGE",
                "authority": "National Payments Corporation of India",
                "title": "UPI Product Page",
                "url": "https://www.npci.org.in/product/upi",
                "publication_date": "DYNAMIC_WEB_PAGE",
                "document_reference": "NPCI UPI product page",
                "source_status": "OFFICIAL_DYNAMIC_SOURCE_REFERENCE",
                "freshness_class": "dynamic_verify_before_demo_or_release",
                "allowed_usage": [
                    "UPI ecosystem orientation",
                    "official NPCI product-page reference",
                    "linking to UPI help and statistics source candidates",
                ],
                "prohibited_usage": [
                    "claiming live integration",
                    "claiming current rules without circular evidence",
                ],
                "extracted_claims": [
                    {
                        "claim_id": "SRC-NPCI-UPI-001",
                        "claim_text": (
                            "NPCI maintains an official UPI product page that links "
                            "to UPI statistics and customer help resources."
                        ),
                        "claim_usage": "ecosystem_reference_prompting",
                        "maps_to_requirement_ids": ["RQ-FUN-004", "RQ-REG-001"],
                        "honesty_labels": ["OFFICIAL_SOURCE_REFERENCE"],
                    },
                ],
            },
        ],
    }


def _source_gap_report(app_id: str) -> dict[str, Any]:
    """Return source gaps that must not be guessed."""

    gaps = [
        {
            "gap_id": "GAP-ECO-001",
            "title": "Current UPI transaction volume and value",
            "why_needed": "Capacity planning and economics sensitivity analysis.",
            "required_source_type": "official NPCI statistics with capture date",
            "current_status": "MISSING_OFFICIAL_SOURCE",
            "allowed_placeholder": "SYNTHETIC_DATA for demo only",
            "blocked_claims": [
                "current UPI volume",
                "current UPI value",
                "year-to-date production sizing",
            ],
        },
        {
            "gap_id": "GAP-ECO-002",
            "title": "Bank internal cost per dispute",
            "why_needed": "Application ROI and manual-ops savings analysis.",
            "required_source_type": "user-provided internal cost model",
            "current_status": "MISSING_OFFICIAL_SOURCE",
            "allowed_placeholder": "SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL",
            "blocked_claims": [
                "rupees saved per real dispute",
                "real bank support cost",
                "real staffing reduction",
            ],
        },
        {
            "gap_id": "GAP-ECO-003",
            "title": "LLM, workflow, storage, and observability runtime prices",
            "why_needed": "Factory run-cost and vendor comparison.",
            "required_source_type": "current vendor pricing or user-provided budget",
            "current_status": "MISSING_OFFICIAL_SOURCE",
            "allowed_placeholder": "relative cost points only",
            "blocked_claims": [
                "exact model run cost",
                "exact monthly SaaS cost",
                "guaranteed cheapest vendor",
            ],
        },
        {
            "gap_id": "GAP-REG-001",
            "title": "Latest amendment or supersession review",
            "why_needed": "Avoid stale regulatory alignment.",
            "required_source_type": "current official circular review",
            "current_status": "MISSING_OFFICIAL_SOURCE",
            "allowed_placeholder": "verify-before-release warning",
            "blocked_claims": [
                "latest RBI rule confirmed",
                "latest NPCI operating rule confirmed",
                "production compliance confirmed",
            ],
        },
        {
            "gap_id": "GAP-APP-001",
            "title": "Live bank, PSP, NPCI, or customer-system API contracts",
            "why_needed": "Production integration design.",
            "required_source_type": "official partner contract and approval",
            "current_status": "MISSING_OFFICIAL_SOURCE",
            "allowed_placeholder": "MOCK_BOUNDARY",
            "blocked_claims": [
                "real bank integration",
                "real NPCI integration",
                "real customer-dispute processing",
            ],
        },
    ]

    return {
        "artifact": "regulatory_economics_source_gap_report.json",
        "app_id": app_id,
        "phase": "Phase 10.1",
        "purpose": "Prevent future prompts from inventing missing regulatory or economic facts.",
        "rule": (
            "If a fact is not source-backed, user-provided, or explicitly synthetic, "
            "it must remain MISSING_OFFICIAL_SOURCE."
        ),
        "gaps": gaps,
    }


def _traceability(app_id: str, registry: dict[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for source in registry["sources"]:
        source_id = str(source["source_id"])
        claim_ids = [
            str(claim["claim_id"])
            for claim in source.get("extracted_claims", [])
            if isinstance(claim, dict)
        ]
        requirement_ids = sorted(
            {
                str(req_id)
                for claim in source.get("extracted_claims", [])
                if isinstance(claim, dict)
                for req_id in claim.get("maps_to_requirement_ids", [])
            }
        )
        rows.append(
            {
                "source_id": source_id,
                "authority": str(source["authority"]),
                "claim_ids": claim_ids,
                "requirement_ids": requirement_ids,
                "phase10_artifact_refs": [
                    "requirements_analysis.json",
                    "domain_analysis.md",
                    "architecture_options.md",
                    "architecture_decision_record.md",
                    "hld.md",
                    "lld.md",
                    "traceability_matrix.json",
                ],
                "phase10_1_artifact_refs": [
                    "official_source_registry.json",
                    "official_source_evidence_pack.md",
                    "source_usage_policy.md",
                    "source_freshness_policy.md",
                    "regulatory_economics_source_gap_report.json",
                ],
                "usage_guardrails": [
                    "No compliance certification claim",
                    "No live payment network call",
                    "No real customer data",
                    "No unsourced ROI or monetary claim",
                ],
            }
        )

    return {
        "artifact": "source_to_requirement_traceability.json",
        "app_id": app_id,
        "phase": "Phase 10.1",
        "traceability_rule": (
            "Each source maps to claims, requirements, artifacts, and usage guardrails."
        ),
        "rows": rows,
    }


def _evidence_pack(app_id: str, registry: dict[str, Any]) -> str:
    lines: list[str] = [
        f"# Phase 10.1 Official Source Evidence Pack — {app_id}",
        "",
        "## Purpose",
        "",
        "This evidence pack records official-source references that may guide",
        "requirements, architecture, economics, and regulatory-alignment prompts.",
        "It is not legal advice, production compliance certification, RBI approval,",
        "NPCI approval, or bank integration evidence.",
        "",
        "## Global honesty labels",
        "",
    ]

    for label in REQUIRED_LABELS:
        lines.append(f"- {label}")

    lines.extend(
        [
            "",
            "## Source-backed references",
            "",
        ]
    )

    for source in registry["sources"]:
        lines.extend(
            [
                f"### {source['source_id']}",
                "",
                f"- Authority: {source['authority']}",
                f"- Title: {source['title']}",
                f"- URL: {source['url']}",
                f"- Publication date: {source['publication_date']}",
                f"- Freshness class: {source['freshness_class']}",
                f"- Source status: {source['source_status']}",
                "",
                "Allowed usage:",
            ]
        )
        for usage in source["allowed_usage"]:
            lines.append(f"- {usage}")

        lines.append("")
        lines.append("Prohibited usage:")
        for usage in source["prohibited_usage"]:
            lines.append(f"- {usage}")

        lines.append("")
        lines.append("Extracted claims:")
        for claim in source["extracted_claims"]:
            lines.append(f"- {claim['claim_id']}: {claim['claim_text']}")
        lines.append("")

    lines.extend(
        [
            "## Economics discipline",
            "",
            "The registry may support economics reasoning only when the value is",
            "source-backed, user-provided, or explicitly synthetic. Current UPI",
            "volume/value, vendor prices, bank internal cost per dispute, staffing",
            "cost, real ROI, penalty exposure, and real customer-impact values must",
            "not be invented.",
            "",
            "## Mock boundary",
            "",
            "NPCI, RBI, bank, PSP, customer, ledger, notification, reconciliation,",
            "and ODR integrations remain MOCK_BOUNDARY unless a future explicitly",
            "approved production integration phase supplies real contracts and",
            "authorization evidence.",
        ]
    )

    return "\n".join(lines)


def _freshness_policy(app_id: str) -> str:
    return f"""
# Phase 10.1 Source Freshness Policy — {app_id}

## Purpose

Prevent stale or unsupported regulatory and economics claims from entering
future prompts, generated artifacts, or demo narratives.

## Freshness classes

| Class | Meaning | Required action |
|---|---|---|
| stable_circular_verify_before_release | Official circular-like reference that changes slowly | Re-check before release/demo/capstone submission |
| dynamic_verify_before_demo_or_release | Official dynamic page | Capture source date before use |
| dynamic_verify_on_every_release | Dynamic values such as product statistics | Re-capture every release if used |
| user_provided_value | Value supplied by the user | Record date, owner, and assumption |
| synthetic_demo_value | Demo-only value | Mark SYNTHETIC_DATA and never present as real |

## Rules

1. Dynamic values cannot be embedded without a capture date.
2. Real ROI cannot be claimed without measured or user-provided values.
3. Real bank cost cannot be claimed without user-provided internal data.
4. Official source titles and URLs may be stored as references.
5. Any current operational rule must be reviewed before production-like claims.
6. MISSING_OFFICIAL_SOURCE is the correct label when evidence is absent.
7. No artifact may claim RBI/NPCI certification or production compliance.

## Release gate

Before any future release that uses a source-backed claim:

- verify the source URL is still accessible
- verify title and publication date
- verify no known supersession has been introduced
- update gap report if the claim is unsupported
- keep all live integrations under MOCK_BOUNDARY
"""


def _usage_policy(app_id: str) -> str:
    return f"""
# Phase 10.1 Source Usage Policy — {app_id}

## Allowed

The factory may use official source references to:

- shape mock requirements
- improve architecture prompts
- improve dispute-domain vocabulary
- identify source-backed design concerns
- identify economics source gaps
- create traceability from source to requirement
- prevent hallucinated regulatory or monetary claims

## Not allowed

The factory must not use source references to claim:

- RBI certification
- NPCI certification
- official regulatory compliance
- production readiness
- legal advice
- real UPI integration
- real bank integration
- real customer-dispute processing
- exact ROI without measured or user-provided data
- live UPI statistics without capture date

## Economics usage

Economic statements must be classified as one of:

- SOURCE_BACKED_REFERENCE
- USER_PROVIDED_VALUE
- SYNTHETIC_DATA
- SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL
- MISSING_OFFICIAL_SOURCE

If none applies, the statement is not allowed.

## Prompting rule

Future agents must prefer this sequence:

1. Use deterministic source-backed fact when available.
2. Use USER_PROVIDED_VALUE when supplied and labelled.
3. Use SYNTHETIC_DATA only for demos.
4. Use MISSING_OFFICIAL_SOURCE rather than guessing.
5. Escalate to human review when the consequence is regulatory, financial,
   customer-impacting, or production-like.
"""


def generate_official_source_artifacts(
    output_dir: Path,
    app_id: str = "upi_dispute_resolution",
) -> list[Path]:
    """Generate Phase 10.1 official-source governance artifacts."""

    output_dir.mkdir(parents=True, exist_ok=True)

    registry = _source_registry(app_id)
    gap_report = _source_gap_report(app_id)
    traceability = _traceability(app_id, registry)

    payloads: dict[str, str | dict[str, Any]] = {
        "official_source_registry.json": registry,
        "official_source_evidence_pack.md": _evidence_pack(app_id, registry),
        "regulatory_economics_source_gap_report.json": gap_report,
        "source_freshness_policy.md": _freshness_policy(app_id),
        "source_usage_policy.md": _usage_policy(app_id),
        "source_to_requirement_traceability.json": traceability,
    }

    written: list[Path] = []
    for filename in REQUIRED_ARTIFACTS:
        if filename == "official_source_validation_report.json":
            continue

        target = output_dir / filename
        payload = payloads[filename]
        if isinstance(payload, dict):
            _write_json(target, payload)
        else:
            _write_markdown(target, payload)
        written.append(target)

    report = validate_official_source_artifacts(output_dir)
    report_path = output_dir / "official_source_validation_report.json"
    _write_json(report_path, report)
    written.append(report_path)

    return written


def _load_json(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"Missing JSON artifact: {path.name}")
        return {}
    except json.JSONDecodeError as exc:
        errors.append(f"Invalid JSON in {path.name}: {exc}")
        return {}

    if not isinstance(loaded, dict):
        errors.append(f"JSON artifact must be an object: {path.name}")
        return {}

    return loaded


def validate_official_source_artifacts(output_dir: Path) -> dict[str, Any]:
    """Validate Phase 10.1 source-governance artifacts."""

    errors: list[str] = []
    warnings: list[str] = []
    checked_artifacts: list[str] = []

    for filename in REQUIRED_ARTIFACTS:
        path = output_dir / filename
        if not path.exists():
            errors.append(f"Missing required artifact: {filename}")
        else:
            checked_artifacts.append(filename)

    registry = _load_json(output_dir / "official_source_registry.json", errors)
    gap_report = _load_json(
        output_dir / "regulatory_economics_source_gap_report.json",
        errors,
    )
    traceability = _load_json(
        output_dir / "source_to_requirement_traceability.json",
        errors,
    )

    text_cache: dict[str, str] = {}
    for filename in REQUIRED_ARTIFACTS:
        path = output_dir / filename
        if path.exists():
            text_cache[filename] = path.read_text(encoding="utf-8")

    combined_text = "\n".join(text_cache.values())

    for label in REQUIRED_LABELS:
        if label not in combined_text:
            errors.append(f"Missing required source-governance label: {label}")

    source_ids: set[str] = set()
    claim_ids: set[str] = set()

    if registry:
        sources = registry.get("sources", [])
        if not isinstance(sources, list) or not sources:
            errors.append("official_source_registry.json must contain sources.")
        else:
            for source in sources:
                if not isinstance(source, dict):
                    errors.append("Each source must be an object.")
                    continue

                source_id = source.get("source_id")
                if not isinstance(source_id, str) or not source_id:
                    errors.append("Each source must have a non-empty source_id.")
                    continue
                source_ids.add(source_id)

                url = source.get("url")
                if not isinstance(url, str) or not url.startswith("https://"):
                    errors.append(f"Source must use https URL: {source_id}")

                if not source.get("authority"):
                    errors.append(f"Source missing authority: {source_id}")

                if not source.get("freshness_class"):
                    errors.append(f"Source missing freshness_class: {source_id}")

                allowed_usage = source.get("allowed_usage", [])
                prohibited_usage = source.get("prohibited_usage", [])
                if not isinstance(allowed_usage, list) or not allowed_usage:
                    errors.append(f"Source missing allowed_usage: {source_id}")
                if not isinstance(prohibited_usage, list) or not prohibited_usage:
                    errors.append(f"Source missing prohibited_usage: {source_id}")

                claims = source.get("extracted_claims", [])
                if not isinstance(claims, list) or not claims:
                    errors.append(f"Source missing extracted_claims: {source_id}")
                    continue

                for claim in claims:
                    if not isinstance(claim, dict):
                        errors.append(f"Claim must be an object: {source_id}")
                        continue

                    claim_id = claim.get("claim_id")
                    if not isinstance(claim_id, str) or not claim_id:
                        errors.append(f"Claim missing claim_id: {source_id}")
                        continue
                    claim_ids.add(claim_id)

                    if not claim.get("claim_text"):
                        errors.append(f"Claim missing claim_text: {claim_id}")

                    claim_labels = claim.get("honesty_labels", [])
                    if not isinstance(claim_labels, list) or not claim_labels:
                        errors.append(f"Claim missing honesty labels: {claim_id}")

                    req_ids = claim.get("maps_to_requirement_ids", [])
                    if not isinstance(req_ids, list) or not req_ids:
                        errors.append(
                            f"Claim missing maps_to_requirement_ids: {claim_id}"
                        )

    missing_sources = [
        source_id for source_id in REQUIRED_SOURCE_IDS
        if source_id not in source_ids
    ]
    for source_id in missing_sources:
        errors.append(f"Missing required source id: {source_id}")

    if gap_report:
        gaps = gap_report.get("gaps", [])
        if not isinstance(gaps, list) or not gaps:
            errors.append("Source gap report must contain gaps.")
        else:
            for gap in gaps:
                if not isinstance(gap, dict):
                    errors.append("Each source gap must be an object.")
                    continue
                gap_id = gap.get("gap_id")
                if not isinstance(gap_id, str) or not gap_id:
                    errors.append("Each source gap must have a gap_id.")
                    continue
                if gap.get("current_status") != "MISSING_OFFICIAL_SOURCE":
                    errors.append(
                        f"Source gap must remain MISSING_OFFICIAL_SOURCE: {gap_id}"
                    )
                if not gap.get("blocked_claims"):
                    errors.append(f"Source gap missing blocked_claims: {gap_id}")

    trace_source_ids: set[str] = set()
    if traceability:
        rows = traceability.get("rows", [])
        if not isinstance(rows, list) or not rows:
            errors.append("Source traceability must contain rows.")
        else:
            for row in rows:
                if not isinstance(row, dict):
                    errors.append("Each traceability row must be an object.")
                    continue
                source_id = row.get("source_id")
                if isinstance(source_id, str):
                    trace_source_ids.add(source_id)
                if not row.get("claim_ids"):
                    errors.append(f"Traceability row missing claim_ids: {source_id}")
                if not row.get("requirement_ids"):
                    errors.append(
                        f"Traceability row missing requirement_ids: {source_id}"
                    )
                if not row.get("usage_guardrails"):
                    errors.append(
                        f"Traceability row missing usage_guardrails: {source_id}"
                    )

    for source_id in sorted(source_ids):
        if source_id not in trace_source_ids:
            errors.append(f"Source missing traceability row: {source_id}")

    # Detect affirmative false claims while allowing guardrail/prohibited-list
    # text. Source-governance artifacts must be allowed to say that something
    # is "not legal advice" or list "real UPI integration" under prohibited
    # claims without failing validation.
    guardrail_markers = (
        "not ",
        "no ",
        "never ",
        "must not ",
        "do not ",
        "cannot ",
        "without ",
        "prohibited",
        "blocked",
        "not allowed",
        "must not use",
        "never claim",
        "not_legal_advice",
        "not_compliance_certification",
        "not_rbi_npci_approval",
    )
    affirmative_markers = (
        " is ",
        " are ",
        " was ",
        " were ",
        " has ",
        " have ",
        " provides ",
        " supports ",
        " enables ",
        " implements ",
        " integrates ",
        " guarantees ",
        " certified",
        " compliant",
        " approval",
        " approved",
    )
    bare_prohibited_terms = {claim.lower() for claim in FORBIDDEN_CLAIMS}

    def is_guardrail_line(normalized_line: str) -> bool:
        if any(marker in normalized_line for marker in guardrail_markers):
            return True

        stripped_line = normalized_line.strip()
        is_markdown_bullet = stripped_line.startswith(("-", "*"))
        is_numbered_bullet = bool(stripped_line[:1].isdigit()) and "." in stripped_line[:4]

        if not (is_markdown_bullet or is_numbered_bullet):
            return False

        bullet_text = stripped_line.lstrip("-*0123456789. ").strip()
        return bullet_text in bare_prohibited_terms

    for line in combined_text.splitlines():
        normalized_line = f" {line.strip().lower()} "
        if not normalized_line.strip():
            continue

        for claim in FORBIDDEN_CLAIMS:
            normalized_claim = claim.lower()
            if normalized_claim not in normalized_line:
                continue

            if is_guardrail_line(normalized_line):
                continue

            claim_is_exact_line = normalized_line.strip() == normalized_claim
            claim_is_affirmed = any(
                marker in normalized_line for marker in affirmative_markers
            )

            if claim_is_exact_line or claim_is_affirmed:
                errors.append(f"Forbidden false claim found: {claim}")

    if "MISSING_OFFICIAL_SOURCE" in combined_text:
        warnings.append(
            "Missing official sources are intentionally visible. Do not replace "
            "them with guessed regulatory, operational, or economic values."
        )

    if "dynamic_verify_on_every_release" in combined_text:
        warnings.append(
            "Dynamic NPCI statistics must be captured with a date before being "
            "used for capacity or economics claims."
        )

    return {
        "artifact": "official_source_validation_report.json",
        "phase": "Phase 10.1",
        "passed": not errors,
        "errors": errors,
        "warnings": warnings,
        "checked_artifacts": checked_artifacts,
        "checked_source_ids": sorted(source_ids),
        "checked_claim_ids": sorted(claim_ids),
        "checked_required_labels": list(REQUIRED_LABELS),
    }
