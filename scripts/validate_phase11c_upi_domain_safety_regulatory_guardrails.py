#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
APP_ID = "upi_dispute_resolution"

PROMPT_RELATIVE_PATHS = [
    "docs/agent_prompt_quality_guide.md",
    "docs/generated_application_quality_prompting_guide.md",
    "docs/prompt_quality_guide.md",
    "factory_governance/00_SYSTEM_PROMPT.md",
    "factory_governance/03_AGENT_ROLE_PROMPTS.md",
    "factory_governance/agent_prompts/common_governed_agent_contract.md",
    "factory_governance/agent_prompts/prompts/architect_agent.md",
    "factory_governance/agent_prompts/prompts/developer_agent.md",
    "factory_governance/agent_prompts/prompts/domain_agent.md",
    "factory_governance/agent_prompts/prompts/evidence_agent.md",
    "factory_governance/agent_prompts/prompts/governance_agent.md",
    "factory_governance/agent_prompts/prompts/operations_agent.md",
    "factory_governance/agent_prompts/prompts/planner_agent.md",
    "factory_governance/agent_prompts/prompts/regeneration_agent.md",
    "factory_governance/agent_prompts/prompts/release_agent.md",
    "factory_governance/agent_prompts/prompts/requirement_agent.md",
    "factory_governance/agent_prompts/prompts/reviewer_agent.md",
    "factory_governance/agent_prompts/prompts/security_agent.md",
    "factory_governance/agent_prompts/prompts/test_agent.md",
    "factory_governance/agent_prompts/prompts/traceability_agent.md",
    "factory_governance/agent_prompts/prompts/validation_agent.md",
    "factory_governance/baseline_original/governed_agentic_factory_final_pack/governed_agentic_factory_final_pack/00_SYSTEM_PROMPT.md",
    "factory_governance/baseline_original/governed_agentic_factory_final_pack/governed_agentic_factory_final_pack/03_AGENT_ROLE_PROMPTS.md",
    "prompts/PHASE_0_1_FACTORY_BUILDER_PROMPT.md",
    "prompts/PHASE_2_ARCHITECTURE_DESIGN_PROMPT.md",
    "prompts/PHASE_3_APP_SHELL_PROMPT.md",
    "prompts/PHASE_4_DISPUTE_INTAKE_PROMPT.md",
    "prompts/PHASE_5_WORKFLOW_DECISION_PROMPT.md",
    "prompts/PHASE_6_FEEDBACK_RELEASE_PROMPT.md",
    "prompts/agents/architecture_agent.md",
    "prompts/agents/governance_reviewer_agent.md",
    "prompts/agents/human_feedback_reviewer_agent.md",
    "prompts/agents/implementation_agent.md",
    "prompts/agents/mock_ecosystem_agent.md",
    "prompts/agents/requirements_analyst.md",
    "prompts/agents/test_validation_agent.md",
    "prompts/phase10/requirement_to_architecture_to_plan_prompt.md",
    "prompts/phase10_1/official_source_evidence_registry_prompt.md",
    "prompts/phase10_2/sdlc_technology_best_practice_prompt.md",
    "prompts/phase10_3/pre_code_generation_readiness_prompt.md",
    "prompts/phase11a/contract_model_agent.md",
    "prompts/phase11a/documentation_agent.md",
    "prompts/phase11a/implementation_planner_agent.md",
    "prompts/phase11a/mock_adapter_agent.md",
    "prompts/phase11a/observability_agent.md",
    "prompts/phase11a/release_readiness_agent.md",
    "prompts/phase11a/security_review_agent.md",
    "prompts/phase11a/service_logic_agent.md",
    "prompts/phase11a/test_generation_agent.md",
    "prompts/phase11a/validation_agent.md",
    "prompts/phase11a_1/essential_agentic_harness_hardening_prompt.md",
    "prompts/phase11a_2/realistic_mock_production_engineering_prompt.md",
    "prompts/phase11b/real_primary_payment_application_mock_ecosystem_prompt.md",
    "prompts/phase11c/requirement_intake_payment_capability_classification_prompt.md",
    "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase10_2/technology_specific_prompt_instructions.md",
    "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase11a_1/prompt_injection_and_untrusted_input_policy.md",
    "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase11a_2/phase11b_prompt_enhancement_contract.md",
]

MARKER = "Phase 11C Mandatory UPI Domain Safety and Regulatory Guardrail Contract"

REQUIRED_TERMS = [
    "real, locally runnable primary UPI/payment dispute-resolution application",
    "mock/simulated",
    "RBI",
    "NPCI",
    "UPI procedural requirements",
    "ODR",
    "failed transaction",
    "TAT",
    "customer compensation",
    "unauthorised electronic banking transaction",
    "RB-IOS",
    "DPDP",
    "PII",
    "Do not claim regulatory compliance",
    "Do not claim that generated artifacts are RBI certified",
    "NPCI certified",
    "Do not use real customer UPI ID",
    "real customer bank account",
    "must not call live NPCI",
    "bank",
    "PSP",
    "payment rail",
    "fraud-risk",
    "unauthorized transaction",
    "idempotency",
    "replay",
    "scenario tests",
    "traceability",
    "unit tests",
    "integration tests",
    "scenario coverage",
    "security review evidence",
    "audit evidence",
    "release-readiness evidence",
    "fail-closed",
    "gap/escalation reporting",
]

FORBIDDEN_POSITIVE_CLAIMS = [
    "RBI certified",
    "NPCI certified",
    "regulator approved",
    "bank approved",
    "production compliant",
    "fully compliant",
    "legally complete",
    "production ready for live UPI",
    "live payment capable",
]


def _is_negated_or_prohibited(text: str, start: int) -> bool:
    window_start = max(0, start - 180)
    before = text[window_start:start].lower()
    same_sentence = re.split(r"[.\n;:]", before)[-1]
    negation_markers = (
        "do not ",
        "must not ",
        "never ",
        "not ",
        "no ",
        "without ",
        "forbid",
        "forbidden",
        "prohibit",
        "prohibited",
        "should not ",
        "cannot ",
        "must never ",
    )
    return any(marker in same_sentence for marker in negation_markers)


def _positive_forbidden_claims(text: str) -> list[dict[str, str]]:
    lowered = text.lower()
    hits: list[dict[str, str]] = []
    for claim in FORBIDDEN_POSITIVE_CLAIMS:
        pattern = re.compile(re.escape(claim.lower()))
        for match in pattern.finditer(lowered):
            if _is_negated_or_prohibited(text, match.start()):
                continue
            start = max(0, match.start() - 90)
            end = min(len(text), match.end() + 90)
            hits.append(
                {
                    "claim": claim,
                    "snippet": " ".join(text[start:end].split()),
                }
            )
    return hits


def _prompt_files() -> list[Path]:
    return [ROOT / rel for rel in PROMPT_RELATIVE_PATHS if (ROOT / rel).exists()]


def validate() -> dict[str, Any]:
    prompt_files = _prompt_files()
    errors: list[dict[str, Any]] = []

    for prompt_file in prompt_files:
        text = prompt_file.read_text(encoding="utf-8")
        missing = [term for term in REQUIRED_TERMS if term not in text]
        positive_forbidden_claims = _positive_forbidden_claims(text)
        if MARKER not in text or missing or positive_forbidden_claims:
            errors.append(
                {
                    "path": str(prompt_file.relative_to(ROOT)),
                    "errors": (
                        ([] if MARKER in text else ["missing_upi_guardrail_contract_section"])
                        + [f"missing_term:{term}" for term in missing]
                    ),
                    "forbidden_positive_claims": positive_forbidden_claims,
                }
            )

    result: dict[str, Any] = {
        "passed": not errors,
        "phase": "Phase 11C",
        "app_id": APP_ID,
        "prompt_files_checked": len(prompt_files),
        "required_terms_checked": len(REQUIRED_TERMS),
        "forbidden_positive_claims_checked": len(FORBIDDEN_POSITIVE_CLAIMS),
        "errors": errors,
    }
    return result


def main() -> int:
    result = validate()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
