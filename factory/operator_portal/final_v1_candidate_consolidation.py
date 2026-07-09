from __future__ import annotations

import json
from pathlib import Path
from typing import Any


APP_ID = "upi_dispute_resolution"
PHASE = "phase45_final_v1_candidate_consolidation"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
GENERATED_APP_ROOT = PROJECT_ROOT / "workspace/factory_generated" / APP_ID / "generated_application"
ARTIFACT_ROOT = PROJECT_ROOT / "workspace/factory_generated" / APP_ID / "lifecycle_artifacts"
ARTIFACT_DIR = ARTIFACT_ROOT / "phase45"

POLICY_PATH = PROJECT_ROOT / "policies/phase45_final_v1_candidate_policy.json"
PROMPT_PATH = PROJECT_ROOT / "prompts/phase45/final_v1_candidate_consolidation_prompt.md"
VALIDATOR_PATH = PROJECT_ROOT / "scripts/validate_phase45_final_v1_candidate_consolidation.py"
GENERATOR_PATH = PROJECT_ROOT / "scripts/generate_phase45_final_v1_candidate_consolidation.py"
TEST_PATH = PROJECT_ROOT / "tests/test_phase45_final_v1_candidate_consolidation.py"
README_PATH = PROJECT_ROOT / "README.md"

FINAL_MANIFEST_PATH = ARTIFACT_DIR / "final_v1_candidate_manifest.json"
RELEASE_GATE_PATH = ARTIFACT_DIR / "final_v1_candidate_release_gate.json"
FINAL_RUNBOOK_PATH = ARTIFACT_DIR / "final_runbook.md"
ARCHITECTURE_SUMMARY_PATH = ARTIFACT_DIR / "architecture_summary.md"
OPERATOR_PORTAL_SUMMARY_PATH = ARTIFACT_DIR / "operator_portal_summary.md"
GENERATED_APP_SUMMARY_PATH = ARTIFACT_DIR / "generated_application_summary.md"
VALIDATION_SUMMARY_PATH = ARTIFACT_DIR / "validation_summary.json"
LIMITATION_STATEMENT_PATH = ARTIFACT_DIR / "limitation_statement.md"
NEXT_ROADMAP_PATH = ARTIFACT_DIR / "next_roadmap.md"
FINAL_EVIDENCE_INDEX_PATH = ARTIFACT_DIR / "final_evidence_index.json"
LOCAL_DEMO_INSTRUCTIONS_PATH = ARTIFACT_DIR / "final_local_demo_instructions.md"
LIFECYCLE_AUDIT_PATH = ARTIFACT_DIR / "phase45_lifecycle_audit.json"

PREPARED_FUTURE_TAG = "v1.0.0-local-governed-upi-factory-candidate"

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

MINIMUM_VALIDATION_COMMANDS = [
    "python scripts/validate_phase45_final_v1_candidate_consolidation.py",
    "python -m pytest tests/test_phase45_final_v1_candidate_consolidation.py",
    "python scripts/validate_phase34_operator_portal_validation_runner.py",
    "python scripts/validate_phase33_operator_portal_evidence_dashboard.py",
    "python scripts/validate_phase32_operator_portal_download_center.py",
    "python scripts/validate_phase31_deep_generated_application_export_download_center.py",
    "python scripts/validate_phase30_deep_generated_application_regeneration.py",
    "python scripts/validate_phase29_generated_application_deep_structure_generator.py",
    "python scripts/validate_phase28_generated_application_architecture_depth_blueprint.py",
    "python -m pytest tests/test_phase34_operator_portal_validation_runner.py",
    "python -m pytest tests/test_phase33_operator_portal_evidence_dashboard.py",
    "python -m pytest tests/test_phase32_operator_portal_download_center.py",
    "python -m pytest tests/test_phase31_deep_generated_application_export_download_center.py",
    "python -m pytest tests/test_phase30_deep_generated_application_regeneration.py",
    "python -m pytest tests/test_phase29_generated_application_deep_structure_generator.py",
    (
        "python -m pytest tests/test_phase11c_agentic_prompt_best_practices.py "
        "tests/test_phase11c_llm_call_metrics_prompt_policy.py "
        "tests/test_phase28_generated_application_architecture_depth_blueprint.py"
    ),
    "python -m ruff check .",
    "python -m mypy .",
]


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


def lifecycle_artifact_paths() -> tuple[Path, ...]:
    return (
        FINAL_MANIFEST_PATH,
        RELEASE_GATE_PATH,
        FINAL_RUNBOOK_PATH,
        ARCHITECTURE_SUMMARY_PATH,
        OPERATOR_PORTAL_SUMMARY_PATH,
        GENERATED_APP_SUMMARY_PATH,
        VALIDATION_SUMMARY_PATH,
        LIMITATION_STATEMENT_PATH,
        NEXT_ROADMAP_PATH,
        FINAL_EVIDENCE_INDEX_PATH,
        LOCAL_DEMO_INSTRUCTIONS_PATH,
        LIFECYCLE_AUDIT_PATH,
    )


def final_manifest() -> dict[str, Any]:
    return {
        "app_id": APP_ID,
        "phase": PHASE,
        "candidate_id": "phase45_final_v1_candidate",
        "candidate_status": "professional_stopping_point",
        "baseline_tag": "v0.44.0-release-evidence-bundle",
        "prepared_future_tag": PREPARED_FUTURE_TAG,
        "future_tag_created": False,
        "future_tag_prepare_only": True,
        "release_gate": relative(RELEASE_GATE_PATH),
        "readme_updated": relative(README_PATH),
        "required_artifacts": [relative(path) for path in lifecycle_artifact_paths()],
        "summary_sections": [
            "final runbook",
            "architecture summary",
            "operator portal summary",
            "generated app summary",
            "validation summary",
            "limitation statement",
            "next-roadmap",
            "final evidence index",
            "final local demo instructions",
        ],
        **safety_boundaries(),
    }


def release_gate() -> dict[str, Any]:
    return {
        "phase": PHASE,
        "gate_id": "PHASE45-FINAL-V1-CANDIDATE-GATE",
        "gate_status": "ready_for_human_review_after_local_validation",
        "automatic_release_actions_enabled": False,
        "criteria": [
            "Phase 45 required files and lifecycle artifacts exist",
            "final v1 candidate manifest and release gate exist",
            "final runbook and local demo instructions exist",
            "README, architecture, operator portal, generated app, validation, limitation, "
            "and roadmap summaries exist",
            "official certification is not claimed",
            "production readiness is not claimed beyond local-readiness evidence",
            "live provider calls are not enabled",
            "real secrets are not created",
            "deployment, merge, tag, and push actions are not enabled",
            "external ecosystem integrations remain mocked or simulated",
        ],
        "manual_next_step": (
            "A future maintainer may create the prepared tag only after independent human "
            "review and the full local validation stack pass."
        ),
        **safety_boundaries(),
    }


def validation_summary() -> dict[str, Any]:
    return {
        "phase": PHASE,
        "validator": relative(VALIDATOR_PATH),
        "tests": relative(TEST_PATH),
        "minimum_validation_commands": MINIMUM_VALIDATION_COMMANDS,
        "validation_claim": "local validation instructions and evidence index only",
        "targeted_phase_coverage": [
            "phase28 generated application architecture depth",
            "phase29 generated application deep structure",
            "phase30 generated application regeneration",
            "phase31 generated application export download center",
            "phase32 operator portal download center",
            "phase33 operator portal evidence dashboard",
            "phase34 operator portal validation runner",
            "phase44 release evidence bundle",
            "phase45 final v1 candidate consolidation",
        ],
        **safety_boundaries(),
    }


def final_evidence_index() -> dict[str, Any]:
    return {
        "phase": PHASE,
        "final_candidate_artifacts": [relative(path) for path in lifecycle_artifact_paths()],
        "policy_and_prompt": [relative(POLICY_PATH), relative(PROMPT_PATH)],
        "validators_and_tests": [
            relative(VALIDATOR_PATH),
            relative(TEST_PATH),
            "scripts/validate_phase44_release_evidence_bundle.py",
            "tests/test_phase44_release_evidence_bundle.py",
        ],
        "operator_portal_evidence": [
            "factory/operator_portal/demo_reviewer_pack.py",
            "factory/operator_portal/validation_runner.py",
            "factory/operator_portal/evidence_dashboard.py",
            "factory/operator_portal/download_center.py",
            "factory/operator_portal/local_web_api.py",
            "factory/operator_portal/web_ui/app.py",
            "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase34/"
            "operator_portal_validation_runner_manifest.json",
            "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase33/"
            "operator_portal_evidence_dashboard_manifest.json",
            "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase32/"
            "operator_portal_download_center_manifest.json",
        ],
        "generated_application_evidence": [
            relative(GENERATED_APP_ROOT / "README.md"),
            relative(GENERATED_APP_ROOT / ".env.example"),
            relative(GENERATED_APP_ROOT / "docs/architecture.md"),
            relative(GENERATED_APP_ROOT / "docs/security_design.md"),
            relative(GENERATED_APP_ROOT / "docs/test_strategy.md"),
            relative(GENERATED_APP_ROOT / "scripts/start_local.sh"),
            relative(GENERATED_APP_ROOT / "scripts/health_check.py"),
            relative(GENERATED_APP_ROOT / "scripts/smoke_test.py"),
            relative(GENERATED_APP_ROOT / "scripts/validate_local_run_pack.py"),
            relative(GENERATED_APP_ROOT / "evidence/generation_summary.json"),
        ],
        "release_evidence_bundle": [
            "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase44/"
            "release_evidence_bundle_manifest.json",
            "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase44/"
            "release_evidence_bundle_index.json",
            "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase44/"
            "release_evidence_bundle_validation_summary.json",
            "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase44/"
            "release_evidence_bundle_boundary_statement.md",
        ],
        **safety_boundaries(),
    }


def lifecycle_audit() -> dict[str, Any]:
    return {
        "phase": PHASE,
        "audit_id": "phase45_final_v1_candidate_lifecycle_audit",
        "status": "consolidated_for_human_review",
        "audited_artifacts": [relative(path) for path in lifecycle_artifact_paths()],
        "non_actions": [
            "no live provider calls",
            "no real secrets",
            "no deployment",
            "no merge",
            "no tag creation",
            "no push",
            "no generated export ZIP creation",
        ],
        **safety_boundaries(),
    }


def final_runbook_markdown() -> str:
    return """# Phase 45 final runbook

This is the final v1.0 candidate consolidation runbook for the governed local
UPI dispute resolution factory.

## Review order

1. Read the final manifest and release gate.
2. Read the final evidence index.
3. Read the architecture, operator portal, and generated application summaries.
4. Run the Phase 45 validator and targeted Phase 45 tests.
5. Run the inherited Phase 28 through Phase 34 validation stack listed in the
   validation summary.
6. Run `python -m ruff check .` and `python -m mypy .`.

## Boundary

The project remains `certification_ready_not_certified`. It does not claim
official certification, regulatory approval, legal sufficiency, live payment
capability, or broad production readiness. Readiness language is limited to
local-readiness evidence.

External UPI rails, banks, NPCI/RBI interfaces, payment rails,
upstream/downstream systems, ODR systems, notification systems, and third-party
services remain mocked or simulated.
"""


def architecture_summary_markdown() -> str:
    return """# Phase 45 architecture summary

The factory is a local-first governed software factory with deterministic
validators, prompt and policy artifacts, lifecycle evidence, and an operator
portal surface for reviewing generated application evidence.

The generated UPI dispute resolution application is maintained as locally
runnable software with API, workflow, security, observability, testing, and local
run-pack artifacts. It intentionally uses mock or simulated ecosystem adapters
for UPI rails, banks, NPCI/RBI interfaces, payment rails, upstream/downstream
systems, and third-party services.

Phase 45 adds a final candidate manifest, final evidence index, release gate,
runbook, demo instructions, limitation statement, and roadmap. It does not add
live connectivity or release automation.
"""


def operator_portal_summary_markdown() -> str:
    return """# Phase 45 operator portal summary

The operator portal evidence surface includes the download center, evidence
dashboard, validation runner, local web API, local web UI, and one-command demo
reviewer pack.

The portal is intended for local review of governance artifacts, generated app
evidence, and validation status. It does not deploy, merge, create release
labels, push, create real secrets, call live providers, or claim official
certification.
"""


def generated_application_summary_markdown() -> str:
    return """# Phase 45 generated application summary

The generated UPI dispute resolution application is locally runnable and
production-disciplined where applicable for a mock-safe local candidate:
structured docs, API/workflow tests, PII-focused checks, smoke tests, local
startup scripts, and validation scripts are present.

The generated application is not connected to live UPI rails, banks, NPCI/RBI
interfaces, payment rails, notification systems, customer systems, or third
party services. Those external ecosystem integrations remain mocked or
simulated.
"""


def limitation_statement_markdown() -> str:
    return """# Phase 45 limitation statement

This repository is certification-ready-not-certified. It is not NPCI certified,
not RBI certified, not bank approved, not legally reviewed for production use,
and not authorized for live payment or dispute processing.

It does not claim broad production readiness. Any readiness evidence is limited
to local-readiness evidence for a governed local candidate with mocked or
simulated external ecosystem integrations.

No real secrets are created. No live provider calls, deployments, merges, release
label creation, pushes, real payment rails, or generated export ZIP creation are
enabled by Phase 45.
"""


def next_roadmap_markdown() -> str:
    return """# Phase 45 next roadmap

1. Independent human review of the final evidence index and release gate.
2. Fresh clone replay of the local validation stack.
3. Manual decision on whether to create the prepared future release label:
   `v1.0.0-local-governed-upi-factory-candidate`.
4. Qualified legal, regulatory, security, and operational review before any
   future live-provider or production-readiness scope is considered.
5. Separate explicit authorization for any real ecosystem integration work.
"""


def local_demo_instructions_markdown() -> str:
    return """# Phase 45 final local demo instructions

Run from the repository root with the project virtual environment activated.

```bash
python scripts/validate_phase45_final_v1_candidate_consolidation.py
python -m pytest tests/test_phase45_final_v1_candidate_consolidation.py
python scripts/validate_phase43_one_command_demo_reviewer_pack.py
python scripts/validate_phase44_release_evidence_bundle.py
```

For generated application local checks, use the committed local run-pack scripts
under `workspace/factory_generated/upi_dispute_resolution/generated_application/`.

This demo is local only. It does not call live providers, create real secrets,
deploy, merge, create release labels, push, or enable live payment rails.
External ecosystem integrations remain mocked or simulated.
"""


def build_final_v1_candidate_bundle() -> dict[str, Any]:
    return {
        "manifest": final_manifest(),
        "release_gate": release_gate(),
        "final_runbook": final_runbook_markdown(),
        "architecture_summary": architecture_summary_markdown(),
        "operator_portal_summary": operator_portal_summary_markdown(),
        "generated_application_summary": generated_application_summary_markdown(),
        "validation_summary": validation_summary(),
        "limitation_statement": limitation_statement_markdown(),
        "next_roadmap": next_roadmap_markdown(),
        "final_evidence_index": final_evidence_index(),
        "local_demo_instructions": local_demo_instructions_markdown(),
        "lifecycle_audit": lifecycle_audit(),
    }


def write_final_v1_candidate_bundle() -> dict[str, Any]:
    bundle = build_final_v1_candidate_bundle()
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    write_json(FINAL_MANIFEST_PATH, bundle["manifest"])
    write_json(RELEASE_GATE_PATH, bundle["release_gate"])
    FINAL_RUNBOOK_PATH.write_text(bundle["final_runbook"], encoding="utf-8")
    ARCHITECTURE_SUMMARY_PATH.write_text(bundle["architecture_summary"], encoding="utf-8")
    OPERATOR_PORTAL_SUMMARY_PATH.write_text(bundle["operator_portal_summary"], encoding="utf-8")
    GENERATED_APP_SUMMARY_PATH.write_text(
        bundle["generated_application_summary"],
        encoding="utf-8",
    )
    write_json(VALIDATION_SUMMARY_PATH, bundle["validation_summary"])
    LIMITATION_STATEMENT_PATH.write_text(bundle["limitation_statement"], encoding="utf-8")
    NEXT_ROADMAP_PATH.write_text(bundle["next_roadmap"], encoding="utf-8")
    write_json(FINAL_EVIDENCE_INDEX_PATH, bundle["final_evidence_index"])
    LOCAL_DEMO_INSTRUCTIONS_PATH.write_text(bundle["local_demo_instructions"], encoding="utf-8")
    write_json(LIFECYCLE_AUDIT_PATH, bundle["lifecycle_audit"])
    return bundle


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def relative(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)
