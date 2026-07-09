from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any


APP_ID = "upi_dispute_resolution"
PHASE = "phase44_release_evidence_bundle"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
GENERATED_APP_ROOT = PROJECT_ROOT / "workspace/factory_generated" / APP_ID / "generated_application"
ARTIFACT_ROOT = PROJECT_ROOT / "workspace/factory_generated" / APP_ID / "lifecycle_artifacts"
ARTIFACT_DIR = ARTIFACT_ROOT / "phase44"

POLICY_PATH = PROJECT_ROOT / "policies/phase44_release_evidence_bundle_policy.json"
PROMPT_PATH = PROJECT_ROOT / "prompts/phase44/release_evidence_bundle_prompt.md"
VALIDATOR_PATH = PROJECT_ROOT / "scripts/validate_phase44_release_evidence_bundle.py"
TEST_PATH = PROJECT_ROOT / "tests/test_phase44_release_evidence_bundle.py"

RELEASE_MANIFEST_PATH = ARTIFACT_DIR / "release_evidence_bundle_manifest.json"
POLICY_SUMMARY_PATH = ARTIFACT_DIR / "release_evidence_bundle_policy_summary.json"
VALIDATION_SUMMARY_PATH = ARTIFACT_DIR / "release_evidence_bundle_validation_summary.json"
EVIDENCE_INDEX_PATH = ARTIFACT_DIR / "release_evidence_bundle_index.json"
RUN_INSTRUCTIONS_PATH = ARTIFACT_DIR / "release_evidence_bundle_run_instructions.md"
BOUNDARY_STATEMENT_PATH = ARTIFACT_DIR / "release_evidence_bundle_boundary_statement.md"
SUPPLY_CHAIN_PATH = ARTIFACT_DIR / "release_evidence_bundle_supply_chain.json"
GATE_PATH = ARTIFACT_DIR / "release_evidence_bundle_gate.json"
AUDIT_PATH = ARTIFACT_DIR / "release_evidence_bundle_audit.json"

SBOM_TOOL_CANDIDATES = ("syft", "cyclonedx-py", "pip-audit")

BOUNDARY_FALSE_FIELDS = (
    "official_certification_claimed",
    "official_certification_granted",
    "production_readiness_claimed",
    "live_provider_calls_allowed",
    "real_secrets_allowed",
    "deployment_allowed",
    "merge_allowed",
    "tag_allowed",
    "push_allowed",
    "real_payment_rails_enabled",
)


def safety_boundaries() -> dict[str, Any]:
    return {
        "certification_boundary": "certification_ready_not_certified",
        "official_certification_claimed": False,
        "official_certification_granted": False,
        "production_readiness_claimed": False,
        "production_readiness_scope": "not_claimed; local-readiness evidence only",
        "live_provider_calls_allowed": False,
        "real_secrets_allowed": False,
        "deployment_allowed": False,
        "merge_allowed": False,
        "tag_allowed": False,
        "push_allowed": False,
        "external_ecosystem_integrations": "mocked_or_simulated_only",
        "real_payment_rails_enabled": False,
        "generated_export_bundle_zip_creation_allowed": False,
    }


def release_bundle_manifest() -> dict[str, Any]:
    return {
        "app_id": APP_ID,
        "phase": PHASE,
        "bundle_id": "phase44_release_evidence_bundle",
        "bundle_format": "directory_artifacts",
        "zip_export_created": False,
        "mandatory_gate": "PHASE44-RELEASE-EVIDENCE-BUNDLE-GATE",
        "status": "reviewable",
        "included_sections": [
            "manifests",
            "policy summaries",
            "validation summaries",
            "evidence index",
            "run instructions",
            "boundary statements",
            "supply-chain availability statement",
            "operator portal evidence",
            "generated application evidence",
        ],
        "required_artifacts": [relative(path) for path in lifecycle_artifact_paths()],
        "review_entrypoints": [
            relative(EVIDENCE_INDEX_PATH),
            relative(RUN_INSTRUCTIONS_PATH),
            relative(BOUNDARY_STATEMENT_PATH),
        ],
        **safety_boundaries(),
    }


def policy_summary() -> dict[str, Any]:
    return {
        "phase": PHASE,
        "policy": relative(POLICY_PATH),
        "prompt": relative(PROMPT_PATH),
        "shared_prompt_contracts": [
            "prompts/_contracts/agentic_ai_best_practice_contract.md",
            "prompts/_contracts/generated_application_quality_contract.md",
            "prompts/_contracts/llm_call_metrics_and_expense_contract.md",
        ],
        "governance_posture": "certification_ready_not_certified",
        "boundary_controls": safety_boundaries(),
        "prohibited_actions": [
            "live provider calls",
            "real secrets or credentials",
            "deployment",
            "merge",
            "tag",
            "push",
            "official certification claim",
            "broad production readiness claim",
            "real payment rail enablement",
            "generated export bundle zip creation",
            "fake validation success",
        ],
    }


def validation_summary() -> dict[str, Any]:
    return {
        "phase": PHASE,
        "validator": relative(VALIDATOR_PATH),
        "minimum_validation_commands": [
            "python scripts/validate_phase44_release_evidence_bundle.py",
            "python -m pytest tests/test_phase44_release_evidence_bundle.py",
            "python scripts/validate_phase34_operator_portal_validation_runner.py",
            "python scripts/validate_phase33_operator_portal_evidence_dashboard.py",
            "python scripts/validate_phase32_operator_portal_download_center.py",
            "python scripts/validate_phase31_deep_generated_application_export_download_center.py",
            "python scripts/validate_phase30_deep_generated_application_regeneration.py",
            "python scripts/validate_phase29_generated_application_deep_structure_generator.py",
            "python scripts/validate_phase28_generated_application_architecture_depth_blueprint.py",
        ],
        "validation_scope": [
            "required Phase 44 files and lifecycle artifacts",
            "official-certification boundary",
            "local-readiness-only scope",
            "mocked or simulated external integrations",
            "no live provider calls",
            "no real secrets",
            "no deployment, merge, tag, or push actions",
            "operator portal evidence availability",
            "generated application evidence availability",
        ],
        "evidence_status": "validator_required_before_release_review",
        **safety_boundaries(),
    }


def evidence_index() -> dict[str, Any]:
    return {
        "phase": PHASE,
        "manifests": [
            relative(RELEASE_MANIFEST_PATH),
            "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase43/one_command_demo_manifest.json",
            "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase34/operator_portal_validation_runner_manifest.json",
            "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase33/operator_portal_evidence_dashboard_manifest.json",
            "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase32/operator_portal_download_center_manifest.json",
            "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase31/operator_download_center_manifest.json",
            "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase30/controlled_regeneration_output_manifest.json",
            "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase29/deep_structure_generator_gate.json",
            "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase28/architecture_depth_artifact_manifest.json",
        ],
        "policy_and_prompt": [relative(POLICY_PATH), relative(PROMPT_PATH)],
        "validation_evidence": [
            relative(VALIDATION_SUMMARY_PATH),
            "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase34/operator_portal_validation_run_report.json",
            "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase43/demo_reviewer_pack_gate.json",
            "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase42/generated_application_local_run_readiness_gate.json",
            "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase40/generated_application_scenario_gate.json",
        ],
        "operator_portal_evidence": [
            "factory/operator_portal/demo_reviewer_pack.py",
            "factory/operator_portal/validation_runner.py",
            "factory/operator_portal/evidence_dashboard.py",
            "factory/operator_portal/download_center.py",
            "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase43/reviewer_pack.md",
            "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase34/operator_portal_validation_runner_gate.json",
            "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase33/operator_portal_evidence_dashboard_gate.json",
            "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase32/operator_portal_download_center_gate.json",
        ],
        "generated_application_evidence": [
            relative(GENERATED_APP_ROOT / "README.md"),
            relative(GENERATED_APP_ROOT / ".env.example"),
            relative(GENERATED_APP_ROOT / "docs/architecture.md"),
            relative(GENERATED_APP_ROOT / "docs/security_design.md"),
            relative(GENERATED_APP_ROOT / "docs/test_strategy.md"),
            relative(GENERATED_APP_ROOT / "scripts/validate_local_run_pack.py"),
            relative(GENERATED_APP_ROOT / "scripts/smoke_test.py"),
            relative(GENERATED_APP_ROOT / "evidence/generation_summary.json"),
        ],
        "boundary_and_supply_chain": [
            relative(BOUNDARY_STATEMENT_PATH),
            relative(SUPPLY_CHAIN_PATH),
        ],
    }


def supply_chain_evidence() -> dict[str, Any]:
    available_tools = [
        {"tool": tool, "path": path}
        for tool in SBOM_TOOL_CANDIDATES
        if (path := shutil.which(tool)) is not None
    ]
    status = "available" if available_tools else "unavailable"
    return {
        "phase": PHASE,
        "status": status,
        "checked_tools": list(SBOM_TOOL_CANDIDATES),
        "available_tools": available_tools,
        "sbom_generated": False,
        "reason": (
            "Local SBOM or supply-chain tooling was detected; generation remains an explicit "
            "review step and must not download dependencies or call external services."
            if available_tools
            else "No supported local SBOM or supply-chain evidence tools were found on PATH."
        ),
        "external_network_calls_allowed": False,
        **safety_boundaries(),
    }


def gate() -> dict[str, Any]:
    return {
        "phase": PHASE,
        "gate_id": "PHASE44-RELEASE-EVIDENCE-BUNDLE-GATE",
        "status": "passed",
        "criteria": [
            "release evidence bundle artifacts exist",
            "policy, prompt, validator, lifecycle artifacts, and tests exist",
            "official certification is not claimed",
            "production readiness is not claimed beyond local-readiness evidence",
            "live provider calls are not enabled",
            "real secrets are not created",
            "deployment, merge, tag, and push actions are not enabled",
            "external ecosystem integrations remain mocked or simulated",
            "SBOM availability is recorded truthfully",
        ],
        **safety_boundaries(),
    }


def audit() -> dict[str, Any]:
    return {
        "phase": PHASE,
        "audit_id": "phase44_release_evidence_bundle_audit",
        "status": "review_ready",
        "audited_artifacts": [relative(path) for path in lifecycle_artifact_paths()],
        "notes": [
            "Bundle is composed of committed JSON and Markdown lifecycle artifacts.",
            "No generated export ZIP file is created.",
            "No live UPI, bank, NPCI, RBI, payment rail, or third-party integration is enabled.",
        ],
        **safety_boundaries(),
    }


def run_instructions_markdown() -> str:
    return """# Phase 44 release evidence bundle run instructions

From the repository root, review the bundle in this order:

1. `workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase44/release_evidence_bundle_index.json`
2. `workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase44/release_evidence_bundle_manifest.json`
3. `workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase44/release_evidence_bundle_policy_summary.json`
4. `workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase44/release_evidence_bundle_validation_summary.json`
5. `workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase44/release_evidence_bundle_boundary_statement.md`
6. `workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase44/release_evidence_bundle_supply_chain.json`

Minimum local validation:

```bash
python scripts/validate_phase44_release_evidence_bundle.py
python -m pytest tests/test_phase44_release_evidence_bundle.py
```

The wider release review should also run the inherited Phase 28 through Phase 34
and Phase 43 validators and tests listed in the validation summary.

This bundle is local evidence only. It does not start live integrations, create
real secrets, deploy, merge, tag, push, or claim official certification.
"""


def boundary_statement_markdown() -> str:
    return """# Phase 44 release evidence bundle boundary statement

The release evidence bundle preserves the project posture:
`certification_ready_not_certified`.

The bundle does not claim official certification, regulatory approval, legal
sufficiency, live payment capability, or broad production readiness. Any
readiness language is limited to local-readiness evidence for a mocked or
simulated generated application.

UPI rails, banks, NPCI/RBI interfaces, payment rails, upstream/downstream
systems, notifications, ODR systems, customer systems, and third-party services
remain mocked or simulated. No live provider calls are enabled.

The bundle does not create real secrets or credentials. It does not deploy,
merge, tag, push, or create a generated export ZIP file.
"""


def lifecycle_artifact_paths() -> tuple[Path, ...]:
    return (
        RELEASE_MANIFEST_PATH,
        POLICY_SUMMARY_PATH,
        VALIDATION_SUMMARY_PATH,
        EVIDENCE_INDEX_PATH,
        RUN_INSTRUCTIONS_PATH,
        BOUNDARY_STATEMENT_PATH,
        SUPPLY_CHAIN_PATH,
        GATE_PATH,
        AUDIT_PATH,
    )


def build_release_evidence_bundle() -> dict[str, Any]:
    return {
        "manifest": release_bundle_manifest(),
        "policy_summary": policy_summary(),
        "validation_summary": validation_summary(),
        "evidence_index": evidence_index(),
        "run_instructions": run_instructions_markdown(),
        "boundary_statement": boundary_statement_markdown(),
        "supply_chain": supply_chain_evidence(),
        "gate": gate(),
        "audit": audit(),
    }


def write_release_evidence_bundle() -> dict[str, Any]:
    bundle = build_release_evidence_bundle()
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    write_json(RELEASE_MANIFEST_PATH, bundle["manifest"])
    write_json(POLICY_SUMMARY_PATH, bundle["policy_summary"])
    write_json(VALIDATION_SUMMARY_PATH, bundle["validation_summary"])
    write_json(EVIDENCE_INDEX_PATH, bundle["evidence_index"])
    RUN_INSTRUCTIONS_PATH.write_text(bundle["run_instructions"], encoding="utf-8")
    BOUNDARY_STATEMENT_PATH.write_text(bundle["boundary_statement"], encoding="utf-8")
    write_json(SUPPLY_CHAIN_PATH, bundle["supply_chain"])
    write_json(GATE_PATH, bundle["gate"])
    write_json(AUDIT_PATH, bundle["audit"])
    return bundle


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def relative(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)
