#!/usr/bin/env python3
# Validate Phase 13AX guided requirement intake UI artifacts.

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

if __package__ in {None, ""}:
    project_root = Path(__file__).resolve().parents[1]
    project_root_text = str(project_root)
    if project_root_text not in sys.path:
        sys.path.insert(0, project_root_text)

from fastapi.testclient import TestClient

from scripts.build_guided_requirement_intake_preview import (
    BLOCKED_ACTIONS,
    PREVIEW_SECTIONS,
    READY,
    REQUIRED_FIELDS,
    build_requirement_intake_preview,
    validate_requirement_intake_preview,
)
from scripts.start_factory_operator_portal import create_app


POLICY_PATH = Path("policies/phase13ax_guided_requirement_intake_ui_policy.json")
DOC_PATH = Path("docs/phase13ax/guided_requirement_intake_ui.md")
PREVIEW_PATH = Path("scripts/build_guided_requirement_intake_preview.py")
PORTAL_PATH = Path("scripts/start_factory_operator_portal.py")
AUDIT_PATH = Path(
    "workspace/factory_generated/upi_dispute_resolution/"
    "lifecycle_artifacts/phase13ax/guided_requirement_intake_ui_audit.json"
)
PHASE13AW_PORTAL = Path("scripts/build_local_operator_portal_status.py")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return cast(dict[str, Any], value)


def sample_payload() -> dict[str, Any]:
    return {
        "business_domain": "UPI dispute resolution",
        "application_name": "upi_dispute_resolution",
        "capabilities": "case intake, dispute triage, evidence tracking, SLA escalation",
        "regulatory_constraints": "NPCI traceability, RBI audit evidence, PII handling",
        "mock_ecosystem": "mock bank rails, mock NPCI switch, mock notifications",
        "data_sensitivity": "regulated payment PII",
        "llm_mode": "offline/replay",
        "approval_mode": "human approval required",
    }


def validate() -> list[str]:
    failures: list[str] = []
    for path in [POLICY_PATH, DOC_PATH, PREVIEW_PATH, PORTAL_PATH, AUDIT_PATH, PHASE13AW_PORTAL]:
        if not path.exists():
            failures.append(f"Missing required artifact: {path}")
    if failures:
        return failures

    policy = load_json(POLICY_PATH)
    audit = load_json(AUDIT_PATH)

    if policy.get("schema_version") != "guided-requirement-intake-ui-policy.v1":
        failures.append("Invalid policy schema_version")
    if policy.get("mode") != "LOCAL_ONLY_REQUIREMENT_INTAKE_PREVIEW_NON_DESTRUCTIVE":
        failures.append("Policy mode mismatch")
    if policy.get("preferred_term") != "application engineering":
        failures.append("Policy must prefer application engineering")
    if policy.get("requires_phase13aw_operator_portal") is not True:
        failures.append("Policy must require Phase 13AW operator portal")
    if policy.get("preview_only") is not True:
        failures.append("Policy must keep preview_only true")

    for key in [
        "live_provider_calls_allowed",
        "external_system_calls_allowed",
        "arbitrary_shell_execution_allowed_from_ui",
        "destructive_delete_allowed_from_ui",
        "real_generated_application_write_allowed_from_ui",
        "requirement_package_write_allowed_from_ui",
        "generation_execution_allowed_from_ui",
        "factory_self_modification_allowed_from_ui",
        "auto_merge_allowed_from_ui",
        "auto_tag_allowed_from_ui",
        "auto_release_allowed_from_ui",
    ]:
        if policy.get(key) is not False:
            failures.append(f"Policy must keep {key} false")

    if set(policy.get("required_intake_fields", [])) != set(REQUIRED_FIELDS):
        failures.append("Policy required fields do not match preview builder")
    if set(policy.get("required_preview_sections", [])) != set(PREVIEW_SECTIONS):
        failures.append("Policy preview sections do not match preview builder")
    for action in BLOCKED_ACTIONS:
        if action not in policy.get("blocked_actions", []):
            failures.append(f"Policy missing blocked action: {action}")

    for key in [
        "live_provider_calls_performed",
        "external_system_calls_performed",
        "arbitrary_shell_execution_exposed_from_ui",
        "real_generated_application_deleted",
        "real_generated_application_overwritten",
        "requirement_package_written_from_ui",
        "application_generation_triggered_from_ui",
        "factory_self_modification_applied",
        "auto_merge_performed",
        "auto_tag_performed",
        "auto_release_performed",
    ]:
        if audit.get(key) is not False:
            failures.append(f"Audit must confirm {key} is false")

    preview = build_requirement_intake_preview(sample_payload())
    if preview.preview_status != READY:
        failures.append(f"Preview should be ready; got {preview.preview_status}")
    failures.extend(validate_requirement_intake_preview(preview))

    blocked = build_requirement_intake_preview({"business_domain": "Payments"})
    if blocked.ready:
        failures.append("Preview with missing fields should be blocked")

    client = TestClient(create_app(Path.cwd()))
    page = client.get("/requirements")
    if page.status_code != 200:
        failures.append("Requirement intake page failed")
    elif "Guided Requirement Intake" not in page.text:
        failures.append("Requirement intake page missing title")

    api = client.post("/api/requirements/preview", json=sample_payload())
    if api.status_code != 200:
        failures.append("Requirement preview API failed")
    else:
        payload = api.json()
        if payload.get("preview_status") != READY:
            failures.append("Requirement preview API did not return ready status")
        if payload.get("application_generation_triggered_from_ui") is not False:
            failures.append("Requirement preview API must not trigger generation")

    cli = subprocess.run(
        [
            sys.executable,
            str(PREVIEW_PATH),
            "--payload-json",
            json.dumps(sample_payload()),
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    if cli.returncode != 0:
        failures.append("Requirement preview CLI should pass")
    elif READY not in cli.stdout:
        failures.append("Requirement preview CLI did not emit ready status")

    doc_text = DOC_PATH.read_text(encoding="utf-8").lower()
    for phrase in [
        "guided requirement intake ui foundation",
        "preview-only",
        "does not delete the real generated application",
        "does not overwrite the real generated application",
        "does not write requirement packages from the ui",
        "does not run application engineering from the ui",
        "portal routes",
        "governance improvement",
    ]:
        if phrase not in doc_text:
            failures.append(f"Documentation missing phrase: {phrase}")
    return failures


def main() -> int:
    failures = validate()
    if failures:
        print("Phase 13AX validation failed:")
        for failure in failures:
            print(f" - {failure}")
        return 1
    print("Phase 13AX guided requirement intake UI artifacts validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
