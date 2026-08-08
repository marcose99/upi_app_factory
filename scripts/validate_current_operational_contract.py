#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.current_operational_contract import (  # noqa: E402
    GENERIC_CONTRACT_RELATIVE_PATH,
    load_application_profile,
    load_contract_registry,
    load_generic_upi_factory_contract,
    recipient_test_command,
    registered_application_ids,
    repository_file,
    required_local_run_environment,
)

EXPECTED_PROTECTED_BOUNDARIES = (
    "SOURCE_OR_DOCUMENTATION_MUTATION",
    "COMMIT",
    "PUSH",
    "MAIN_DELIVERY_OR_MERGE",
    "FORCE_PUSH",
    "TAG_OR_RELEASE",
    "DEPLOYMENT",
    "CERTIFICATION_CLAIM",
    "LIVE_PROVIDER_OR_PAYMENT_ACCESS",
)

DOCUMENTATION_MATRIX_PATH = "docs/documentation/DOCUMENTATION_EVIDENCE_MATRIX.json"


def _validate_generic_contract(
    generic: dict[str, Any],
    errors: list[str],
) -> None:
    scope = generic.get("scope")
    if not isinstance(scope, dict):
        errors.append("generic contract scope must be an object")
        return
    if scope.get("application_family") != "UPI":
        errors.append("generic contract must apply to the UPI application family")
    if scope.get("application_specific_runtime_details_permitted") is not False:
        errors.append("generic contract must not contain application-specific runtime details")

    encoded = json.dumps(generic, sort_keys=True).lower()
    for forbidden in ("upi_dispute_resolution", "upi_dispute_", "beneficiary-not-credited"):
        if forbidden in encoded:
            errors.append(
                f"generic UPI factory contract contains application-specific detail: "
                f"{forbidden}"
            )

    architecture = generic.get("architecture")
    if not isinstance(architecture, dict):
        errors.append("generic contract architecture must be an object")
        return
    if architecture.get("control_plane_separate_from_generated_application_runtime") is not True:
        errors.append("generic contract lost control-plane/runtime separation")
    if architecture.get("generated_applications_must_be_independently_reproducible") is not True:
        errors.append("generic contract lost generated-app reproducibility requirement")
    if architecture.get("generated_application_root_template") != (
        "workspace/factory_generated/{application_id}/generated_application"
    ):
        errors.append("generic contract generated-application root template is not canonical")

    security = generic.get("security_policy")
    if not isinstance(security, dict):
        errors.append("generic contract security_policy must be an object")
    else:
        if security.get("real_payment_calls_default") != "disabled":
            errors.append("generic contract changed real-payment safety default")
        if security.get("live_llm_provider_default") != "disabled":
            errors.append("generic contract changed live-LLM safety default")
        if security.get("real_secrets_allowed_in_acceptance") is not False:
            errors.append("generic contract permits real secrets in acceptance")

    governance = generic.get("governance")
    if not isinstance(governance, dict):
        errors.append("generic contract governance must be an object")
    else:
        boundaries = governance.get("protected_boundaries")
        if boundaries != list(EXPECTED_PROTECTED_BOUNDARIES):
            errors.append("generic contract protected boundaries are not durable/stable")
        encoded_boundaries = json.dumps(boundaries).lower()
        for campaign_term in (
            "documentation_reconstruction",
            "current_contract_and_validator_modernization",
            "rc_requalification",
            "rc1_tag_publication",
        ):
            if campaign_term in encoded_boundaries:
                errors.append(
                    f"generic contract contains campaign-specific protected boundary: "
                    f"{campaign_term}"
                )

    requirements = generic.get("generated_application_profile_requirements")
    if not isinstance(requirements, dict):
        errors.append(
            "generic contract generated_application_profile_requirements must be an object"
        )
        return
    required_fields = requirements.get("required_fields")
    if not isinstance(required_fields, list):
        errors.append("generic contract required_fields must be a list")
    else:
        for field in (
            "schema_version",
            "application_id",
            "upi_application_type",
            "inherits_generic_contract",
            "recipient_test",
            "local_acceptance_environment",
            "runtime_safety",
            "documentation",
        ):
            if field not in required_fields:
                errors.append(f"generic contract profile requirements missing field: {field}")

    safety_false_fields = requirements.get("runtime_safety_required_false_fields")
    if not isinstance(safety_false_fields, list) or not safety_false_fields:
        errors.append("generic contract runtime safety false-field list is missing")
    else:
        for field in (
            "live_provider_calls_allowed",
            "real_payment_calls_allowed",
            "real_secrets_allowed",
            "deployment_allowed",
            "merge_allowed",
            "push_allowed",
            "force_push_allowed",
            "tag_allowed",
            "release_allowed",
            "certification_claim_allowed",
        ):
            if field not in safety_false_fields:
                errors.append(
                    f"generic contract runtime safety false-field list missing: {field}"
                )


def _validate_factory_executable_truth(
    generic: dict[str, Any],
    errors: list[str],
) -> None:
    run_factory = (PROJECT_ROOT / "run_factory.sh").read_text(encoding="utf-8")
    for marker in (
        "127.0.0.1",
        "localhost",
        "REAL_PAYMENT_CALLS=disabled",
        "FACTORY_LLM_ENABLED=0",
    ):
        if marker not in run_factory:
            errors.append(f"run_factory.sh missing generic contract marker: {marker}")

    compose = (PROJECT_ROOT / "compose.yaml").read_text(encoding="utf-8")
    for marker in ("127.0.0.1:", "read_only: true", "/health", "MOCK_BOUNDARY"):
        if marker not in compose:
            errors.append(f"compose.yaml missing generic contract marker: {marker}")

    governance = generic.get("governance")
    if not isinstance(governance, dict):
        errors.append("generic contract governance must be an object")
        return
    jobs = governance.get("governed_ci_jobs")
    if not isinstance(jobs, list) or not all(isinstance(job, str) for job in jobs):
        errors.append("generic contract governed_ci_jobs must contain strings")
        return

    workflow = (PROJECT_ROOT / ".github/workflows/governed-ci.yml").read_text(
        encoding="utf-8"
    )
    for job_name in jobs:
        if f"name: {job_name}" not in workflow and f'name: "{job_name}"' not in workflow:
            errors.append(f"Governed CI workflow missing generic contract job: {job_name}")


def _generated_app_root(
    generic: dict[str, Any],
    application_id: str,
) -> Path:
    architecture = generic.get("architecture")
    if not isinstance(architecture, dict):
        raise ValueError("generic contract architecture must be an object")
    template = architecture.get("generated_application_root_template")
    if not isinstance(template, str):
        raise ValueError("generated application root template must be a string")
    if template != "workspace/factory_generated/{application_id}/generated_application":
        raise ValueError("generated application root template is not canonical")
    relative = template.format(application_id=application_id)
    root = (PROJECT_ROOT / relative).resolve()
    try:
        root.relative_to(PROJECT_ROOT.resolve())
    except ValueError as exc:
        raise ValueError("generated application root escapes project root") from exc
    if not root.is_dir():
        raise ValueError(f"generated application root is missing for {application_id}")
    return root


def _validate_application_profile(
    generic: dict[str, Any],
    application_id: str,
    profile: dict[str, Any],
    errors: list[str],
) -> None:
    requirements = generic.get("generated_application_profile_requirements")
    if not isinstance(requirements, dict):
        errors.append("generic profile requirements must be an object")
        return

    required = requirements.get("required_fields")
    if not isinstance(required, list):
        errors.append("generic required_fields must be a list")
        return
    for field in required:
        if not isinstance(field, str):
            errors.append("generic required_fields contains a non-string entry")
        elif field not in profile:
            errors.append(
                f"{application_id}: application profile missing generic required field: "
                f"{field}"
            )

    if profile.get("application_id") != application_id:
        errors.append(f"{application_id}: application profile identity mismatch")
    if profile.get("inherits_generic_contract") != GENERIC_CONTRACT_RELATIVE_PATH:
        errors.append(
            f"{application_id}: application profile does not inherit generic UPI "
            "factory contract"
        )

    safety = profile.get("runtime_safety")
    if not isinstance(safety, dict):
        errors.append(f"{application_id}: runtime_safety must be an object")
    else:
        false_fields = requirements.get("runtime_safety_required_false_fields")
        if not isinstance(false_fields, list):
            errors.append("generic runtime safety false-field list must be a list")
        else:
            for field in false_fields:
                if not isinstance(field, str):
                    errors.append("generic runtime safety field list contains non-string")
                elif safety.get(field) is not False:
                    errors.append(
                        f"{application_id}: application profile weakens safety field: "
                        f"{field}"
                    )

    try:
        generated_root = _generated_app_root(generic, application_id)
        env_example_path = generated_root / ".env.example"
        if not env_example_path.is_file():
            errors.append(f"{application_id}: generated .env.example is missing")
        else:
            env_example = env_example_path.read_text(encoding="utf-8")
            for value in required_local_run_environment(application_id, profile):
                if value not in env_example:
                    errors.append(
                        f"{application_id}: generated .env.example missing profile "
                        f"value: {value}"
                    )
    except (OSError, ValueError) as exc:
        errors.append(f"{application_id}: generated application validation failed: {exc}")

    documentation = profile.get("documentation")
    if not isinstance(documentation, dict):
        errors.append(f"{application_id}: documentation must be an object")
        return
    deployment_guide = documentation.get("deployment_guide")
    if not isinstance(deployment_guide, str):
        errors.append(f"{application_id}: deployment guide path is missing")
        return

    try:
        deployment_guide_path = repository_file(
            deployment_guide,
            required_prefix="docs/deployment",
        )
        deployment_guide_text = deployment_guide_path.read_text(encoding="utf-8")
        command = recipient_test_command(application_id, profile)
        if command not in deployment_guide_text:
            errors.append(
                f"{application_id}: deployment guide missing profile recipient "
                f"command: {command}"
            )
        if "python -m pytest -q generated_application/app/tests" in deployment_guide_text:
            errors.append(
                f"{application_id}: deployment guide contains stale nested test path"
            )
    except (OSError, ValueError) as exc:
        errors.append(f"{application_id}: deployment guide validation failed: {exc}")


def _validate_documentation_evidence_matrix(errors: list[str]) -> None:
    try:
        matrix_path = repository_file(
            DOCUMENTATION_MATRIX_PATH,
            required_prefix="docs/documentation",
        )
        payload = json.loads(matrix_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"documentation evidence matrix is not valid JSON: {exc}")
        return

    if not isinstance(payload, dict):
        errors.append("documentation evidence matrix must be a JSON object")
        return
    if payload.get("schema_version") != "upi-app-factory.documentation-evidence-matrix.v1":
        errors.append("documentation evidence matrix schema is unsupported")

    documents = payload.get("documents")
    if not isinstance(documents, list):
        errors.append("documentation evidence matrix documents must be a list")
        return
    if payload.get("document_count") != len(documents):
        errors.append("documentation evidence matrix document_count is stale")
    if payload.get("total_information_item_count") != len(documents) + 1:
        errors.append("documentation evidence matrix total information item count is stale")

    seen: set[str] = set()
    for index, entry in enumerate(documents):
        if not isinstance(entry, dict):
            errors.append(f"documentation matrix row {index} must be an object")
            continue
        relative = entry.get("path")
        expected_sha = entry.get("sha256_after")
        if not isinstance(relative, str) or not relative:
            errors.append(f"documentation matrix row {index} has invalid path")
            continue
        if relative in seen:
            errors.append(f"documentation matrix has duplicate path: {relative}")
            continue
        seen.add(relative)
        if not isinstance(expected_sha, str) or len(expected_sha) != 64:
            errors.append(f"documentation matrix has invalid current SHA-256: {relative}")
            continue
        try:
            document_path = repository_file(relative)
        except ValueError as exc:
            errors.append(f"documentation matrix path validation failed: {exc}")
            continue
        actual_sha = hashlib.sha256(document_path.read_bytes()).hexdigest()
        if actual_sha != expected_sha:
            errors.append(
                f"documentation matrix SHA-256 drift: {relative}: "
                f"{expected_sha} != {actual_sha}"
            )


def validate() -> dict[str, Any]:
    errors: list[str] = []
    registry_schema: str | None = None
    generic_schema: str | None = None
    application_profile_schemas: dict[str, str] = {}
    application_ids: list[str] = []
    validated_application_ids: list[str] = []

    try:
        registry = load_contract_registry()
        registry_schema_value = registry.get("schema_version")
        if isinstance(registry_schema_value, str):
            registry_schema = registry_schema_value

        generic = load_generic_upi_factory_contract()
        generic_schema_value = generic.get("schema_version")
        if isinstance(generic_schema_value, str):
            generic_schema = generic_schema_value

        application_ids = list(registered_application_ids(registry))

        _validate_generic_contract(generic, errors)
        _validate_factory_executable_truth(generic, errors)

        for application_id in application_ids:
            try:
                profile = load_application_profile(application_id)
                schema = profile.get("schema_version")
                if isinstance(schema, str):
                    application_profile_schemas[application_id] = schema
                _validate_application_profile(
                    generic,
                    application_id,
                    profile,
                    errors,
                )
                validated_application_ids.append(application_id)
            except (OSError, ValueError, KeyError, TypeError) as exc:
                errors.append(
                    f"{application_id}: application profile validation failed: {exc}"
                )

        documentation_policy = generic.get("documentation_policy")
        if not isinstance(documentation_policy, dict):
            errors.append("generic contract documentation_policy must be an object")
        else:
            canonical_index = documentation_policy.get("canonical_index")
            if not isinstance(canonical_index, str):
                errors.append("canonical documentation index path is missing")
            else:
                try:
                    repository_file(canonical_index, required_prefix="docs")
                except ValueError as exc:
                    errors.append(f"canonical documentation index invalid: {exc}")

        _validate_documentation_evidence_matrix(errors)

    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        errors.append(f"current operational contract loading failed closed: {exc}")

    single_profile_schema = (
        application_profile_schemas.get(application_ids[0])
        if len(application_ids) == 1
        else None
    )
    return {
        "passed": not errors,
        "registry_schema": registry_schema,
        "generic_contract_schema": generic_schema,
        "application_profile_schema": single_profile_schema,
        "application_profile_schemas": application_profile_schemas,
        "application_id": application_ids[0] if len(application_ids) == 1 else None,
        "application_ids": application_ids,
        "validated_application_ids": validated_application_ids,
        "errors": errors,
    }


def main() -> int:
    result = validate()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
