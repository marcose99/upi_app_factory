#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass
from html import escape
import hashlib
import json
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


SCHEMA_VERSION = "upi-app-factory.factory-documentation.v1"
DETERMINISTIC_GENERATED_AT_UTC = "1970-01-01T00:00:00Z"
SUPPLEMENTAL_REPORT_FILENAMES = (
    "agents_ai_capabilities.json",
    "architecture_foundations.json",
    "discovery_summary.json",
    "governance_reliability.json",
    "portal_quality_deployment.json",
)
LEGACY_SOURCE_PATHS = (
    "factory/operator_portal/local_web_api.py",
    "factory/operator_portal/debug_plan_api.py",
    "factory/operator_portal/documentation_api.py",
    "factory/operator_portal/web_ui/app.py",
    "factory/operator_portal/web_ui/static/index.html",
    "factory/operator_portal/web_ui/static/app.js",
    "factory/operator_portal/browser_intake_orchestration.py",
    "factory/debugging/debug_plan.py",
    "factory/operator_portal/portfolio_api.py",
    "factory/operator_portal/runtime_api.py",
    "scripts/run_portal_requirements_driven_application_engineering.py",
    "scripts/build_factory_debug_plan.py",
    "scripts/validate_debug_plan.py",
    "scripts/build_operator_portal_exhaustive_ui_manifest.py",
    "scripts/build_factory_complete_documentation.py",
    "start_factory.sh",
    "stop_factory.sh",
    "config/factory_runtime.env.example",
)
REQUIRED_TOPICS = (
    "Executive technical summary",
    "Truth and trust boundaries",
    "System context",
    "Runtime topology",
    "Repository architecture",
    "Agent and task ownership",
    "Requirements compilation",
    "LLM and prompt strategy",
    "Knowledge retrieval",
    "Tool routing and safeguards",
    "Planning, memory, and adaptation",
    "Operator portal lifecycle",
    "Generated application architecture",
    "Persistence and consistency",
    "Governance and evidence",
    "Security engineering",
    "Observability and debugging",
    "Testing and quality gates",
    "Deployment and portability",
    "Failure modes and recovery",
    "Limitations and non-claims",
    "Source traceability",
)
SECTION_CLAIMS = {
    "Executive technical summary": ("requirements-ir", "portal-api-routes", "GR-001", "C10"),
    "Truth and trust boundaries": ("portal-boundaries", "generated-app-boundaries", "deployment-nonclaims", "C10"),
    "System context": ("startup-routes", "portal-api-routes", "generated-app-api", "state-roots"),
    "Runtime topology": ("runtime-supervision", "runtime-api", "runtime-network-guardrails", "logs-metrics"),
    "Repository architecture": ("kernel-substrate", "generated-app", "native-bootstrap", "docker-route"),
    "Agent and task ownership": ("C02", "C03", "C04", "C06"),
    "Requirements compilation": ("requirements-ir", "requirements-fail-closed", "deep-composer", "generated-routes-composer"),
    "LLM and prompt strategy": ("C09", "C10", "C11", "C13", "C14"),
    "Knowledge retrieval": ("C15", "C20", "C21"),
    "Tool routing and safeguards": ("validation-allowlist", "C05", "C19", "validation-runner-allowlist"),
    "Planning, memory, and adaptation": ("planning-approval", "browser-run-flow", "C16", "C17"),
    "Operator portal lifecycle": ("browser-state-machine", "browser-run-flow", "execution-fail-closed", "browser-downloads"),
    "Generated application architecture": ("generated-app", "generated-app-api", "generated-app-settings", "generated-app-boundaries"),
    "Persistence and consistency": ("kernel-substrate", "kernel-test-proof", "generated-persistence", "GR-003", "GR-011"),
    "Governance and evidence": ("GR-001", "GR-002", "GR-003", "GR-004", "runtime-evidence"),
    "Security engineering": ("GR-008", "GR-009", "GR-015", "GR-018", "C18"),
    "Observability and debugging": ("logs-metrics", "runtime-evidence", "GR-010", "GR-015"),
    "Testing and quality gates": ("generated-test-openapi-gates", "runtime-scenarios", "kernel-test-proof", "public-clone-readiness"),
    "Deployment and portability": ("native-bootstrap", "docker-route", "platform-boundary", "deployment-nonclaims"),
    "Failure modes and recovery": ("GR-006", "GR-007", "C22", "C23", "execution-fail-closed"),
    "Limitations and non-claims": ("deployment-nonclaims", "C24", "GR-014", "platform-boundary"),
    "Source traceability": ("commit-identity", "C01", "GR-017"),
}
REPOSITORY_CLAIM_SPECS: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    ("commit-identity", "Tracked Guide Identity", "The complete guide is generated with deterministic metadata and source hashes rather than runtime repository metadata claims.", ("scripts/build_factory_complete_documentation.py", "schemas/factory_documentation.schema.json")),
    ("C01", "Tracked Baseline Provenance", "Tracked governance provenance files document project lineage boundaries without serializing repository metadata as claim evidence.", ("factory_governance/baseline_provenance_manifest.json", "factory/validators/validate_baseline_provenance.py")),
    ("C02", "Role-Agent Prompt Pack", "A governed prompt-backed role-agent simulation is implemented and test-covered for 15 deterministic agents.", ("factory/agents/contracts.py", "factory_governance/agent_prompts/agent_prompt_manifest.json", "tests/test_phase8_multi_agent_simulation.py")),
    ("C03", "Deterministic Simulation Boundary", "Phase 8 agent execution is deterministic simulation, not autonomous LLM/tool execution.", ("factory/agents/role_runner.py",)),
    ("C04", "Phase 11A Harness", "Phase 11A implements an agentic generation harness and prompt registry, but its executable route is deterministic shadow mode with zero LLM/network calls and no implementation writes.", ("src/upi_factory/agentic_code_generation/harness.py",)),
    ("C05", "Tool Authorization Boundaries", "Phase 11A tool and execution policy enforce approval gates and preserve mock/no-live-payment/no-certification boundaries.", ("src/upi_factory/agentic_code_generation/harness.py",)),
    ("C06", "Runtime Core", "The Phase 13C runtime core is implemented and test-covered as an 8-agent, 7-tool dry-run/local deterministic orchestrator with ledgers.", ("src/factory_agent_runtime/contracts.py", "src/factory_agent_runtime/orchestrator.py", "src/factory_agent_runtime/registry.py", "tests/test_phase13c_agent_runtime_foundation.py")),
    ("C07", "Adapter Detection Boundary", "Adapter capability detection recognizes local, LangGraph, and OpenAI Agents paths, but default execution is local deterministic only.", ("src/factory_agent_runtime/adapters.py", "tests/test_phase13d_agent_adapter_execution.py")),
    ("C08", "LangGraph Boundary Proof", "A LangGraph adapter-boundary proof is implemented and test-specified as a contract demonstration rather than broad production workflow proof.", ("policies/phase13x_agent_runtime_abstraction_policy.json", "scripts/run_phase13x_agent_runtime_abstraction_layer.py", "tests/test_phase13x_agent_runtime_abstraction_layer.py")),
    ("C09", "LLM Provider Readiness", "The LLM provider abstraction is implemented and test-covered as secret-safe deterministic local execution with OpenAI configuration-only readiness.", ("scripts/run_phase13y_llm_provider_abstraction_secret_safe_openai_readiness.py", "tests/test_phase13y_llm_provider_abstraction_secret_safe_openai_readiness.py")),
    ("C10", "LLM Usage Policy", "Repository policy makes LLM use disabled by default, deterministic-first, bounded, batched, schema-constrained, and independently validated.", ("policies/llm_usage_policy.yaml",)),
    ("C11", "LLM Metrics Contract", "Prompt and LLM metrics and expense contracts are implemented and test-covered at the prompt-policy level.", ("src/upi_factory/llm_call_metrics_contract.py", "tests/test_phase11c_llm_call_metrics_prompt_policy.py")),
    ("C12", "Prompt Hashing", "Phase 66 prompt versioning and prompt hashes are implemented and test-covered.", ("src/upi_factory/rubric_alignment/prompts.py", "tests/test_phase66_rubric_alignment.py")),
    ("C13", "Fake LLM Tests", "Phase 66 deterministic fake LLM behavior, schema rejection, timeout/failure handling, and retry exhaustion are implemented and test-covered.", ("src/upi_factory/rubric_alignment/providers.py", "tests/test_phase66_rubric_alignment.py")),
    ("C14", "Live LLM Guard", "Live OpenAI Phase 66 evaluation is implemented as an optional guarded route, not default execution.", ("scripts/run_phase66_live_openai_evaluation.py", "src/upi_factory/rubric_alignment/live.py", "src/upi_factory/rubric_alignment/providers.py", "tests/test_phase66_rubric_alignment.py")),
    ("C15", "Retrieval Boundary", "Retrieval and embeddings are implemented for Phase 66 using deterministic fake embeddings by default, with optional OpenAI embeddings in the live path.", ("src/upi_factory/rubric_alignment/retrieval.py", "tests/test_phase66_rubric_alignment.py")),
    ("C16", "Run-Scoped Memory", "Memory retention/reset behavior is implemented and test-covered as an in-memory run-scoped Phase 66 demo.", ("src/upi_factory/rubric_alignment/memory.py", "tests/test_phase66_rubric_alignment.py")),
    ("C17", "Feedback Boundary", "Feedback capture exists in the generated app and Phase 66 demo, but adaptive behavior is limited and policy-filtered.", ("app/feedback/repository.py", "app/feedback/routes.py", "src/upi_factory/rubric_alignment/memory.py", "tests/feedback/test_feedback_submission.py", "tests/test_phase66_rubric_alignment.py")),
    ("C18", "Safety Refusals", "Loop and safety safeguards include deterministic refusal or escalation for live-payment, secret, destructive, approval-bypass, regulatory-claim, prompt-injection, PII, and low-confidence cases.", ("src/upi_factory/rubric_alignment/safety.py", "tests/test_phase66_rubric_alignment.py")),
    ("C19", "Tool Routing", "Phase 66 has a deterministic tool-routing function with test proof for retrieval routing, but not a general dynamic tool-execution framework.", ("src/upi_factory/rubric_alignment/tool_routing.py", "tests/test_phase66_rubric_alignment.py")),
    ("C20", "Offline Evaluation Evidence", "Phase 66 offline evaluation is implemented, test-covered, and has tracked evidence artifacts.", ("src/upi_factory/rubric_alignment/benchmark.py", "tests/test_phase66_rubric_alignment.py", "evidence/phase66/offline/manifest.json", "evidence/phase66/offline/offline_summary.json", "evidence/phase66/offline/SHA256SUMS")),
    ("C21", "Governance Policies", "Governance policies preserve local-first, no-live-payment, no-real-customer-data, no-secret, and citation/provenance boundaries.", ("docs/phase11d/memory_retrieval_context_policy.json", "docs/phase11d/tool_authorization_policy.json")),
    ("C22", "Self Correction Boundary", "Self-correction is implemented and test-covered as bounded deterministic triage, not unrestricted autonomous repair.", ("src/factory_agent_runtime/self_correction.py", "tests/test_phase13c_self_correction_governance.py")),
    ("C23", "Supervisor Repair Limits", "Autonomous supervisor loops are bounded by config and fail closed for unknown or exhausted repairs.", ("config/autonomous/repair_catalog.json", "config/autonomous/supervisor_limits.json", "tools/autonomous_supervisor/engine.py")),
    ("C24", "Certification Non-Claim", "The repository preserves certification-ready-not-certified wording and does not provide actual regulatory certification, approval, or production readiness evidence.", ("config/technical_identity_contract.json", "docs/deployment/DEPLOYMENT_BOUNDARIES_AND_NON_CLAIMS.md", "README.md")),
    ("canonical-identity", "Canonical Identity", "The requirements compiler enforces UPI App Factory canonical identity for the factory-level IR.", ("factory/application_engineering/requirements_compiler.py",)),
    ("requirements-ir", "Requirements IR", "Requirements compilation is implemented as deterministic Markdown-to-JSON IR normalization with diagnostics, traceability, and SHA-256 canonical hashing, with automated test proof for the fixture path.", ("factory/application_engineering/requirements_compiler.py", "tests/test_phase53_requirements_compiler.py")),
    ("requirements-fail-closed", "Requirements Fail Closed", "The requirements compiler fails closed on identity errors, duplicate IDs, empty required collections, unsupported dependencies, and live-payment contradictions.", ("factory/application_engineering/requirements_compiler.py", "tests/test_phase53_requirements_compiler.py")),
    ("deep-composer", "Deep Composer", "The deep composer is an implemented deterministic generator for a local mock-only golden failed-debit dispute app, with automated tests for profile, boundaries, endpoints, files, and namespace rejection.", ("factory/application_engineering/deep_composer.py", "tests/test_phase56_deep_composer.py")),
    ("generated-routes-composer", "Generated Route Composer", "The composer-generated golden app route inventory is explicit in generated source and OpenAPI metadata, and is tested by source inspection.", ("factory/application_engineering/deep_composer.py", "tests/test_phase56_deep_composer.py")),
    ("kernel-substrate", "Local Kernel", "The local platform kernel provides SQLite-backed migration, idempotency, audit, outbox, versioned repository, authorization, redacting logging, metrics, and health primitives.", ("factory/application_engineering/local_platform_kernel.py",)),
    ("kernel-test-proof", "Kernel Tests", "The local platform kernel has automated tests for key persistence, audit, idempotency, observability, authorization, and determinism behaviors.", ("tests/test_phase54_local_platform_kernel.py",)),
    ("state-roots", "State Roots", "Portal and runtime state roots are configurable and local-first, with defaults under the worktree and path-boundary checks on runtime state.", ("factory/operator_portal/runtime_store.py", "factory/operator_portal/state_roots.py")),
    ("portal-boundaries", "Portal Boundaries", "The operator portal exposes executable safety-boundary metadata preserving local-only, certification-ready-not-certified, no-live-provider, no-secret, no-deployment, and no-release-action boundaries.", ("factory/operator_portal/local_web_api.py", "tests/test_phase35_operator_portal_local_web_api.py")),
    ("startup-routes", "Startup Routes", "The operator portal startup surface is FastAPI-based, with local API routes plus a local static web UI wrapper.", ("factory/operator_portal/local_web_api.py", "factory/operator_portal/web_ui/app.py")),
    ("validation-allowlist", "Validation Allowlist", "The portal validation runner is governed by command IDs and fixed argv, not arbitrary shell text, and reports safety boundaries in its output.", ("factory/operator_portal/validation_runner.py",)),
    ("browser-intake", "Browser Intake", "Browser-driven requirements intake is run-scoped, size-bounded, secret-aware, hash-recorded, and guarded by deterministic validation.", ("factory/operator_portal/browser_intake_orchestration.py", "tests/test_phase49a_browser_driven_intake_orchestration.py")),
    ("planning-approval", "Planning Approval", "Application engineering through the portal is a governed state-machine flow requiring plan creation and run-scoped approval before execution.", ("factory/operator_portal/browser_intake_orchestration.py", "tests/test_phase49a_browser_driven_intake_orchestration.py")),
    ("runtime-contracts", "Runtime Contracts", "Runtime control has explicit state transitions and scoped approval digest contracts with automated tests.", ("factory/operator_portal/runtime_contracts.py", "tests/phase50/test_runtime_contracts.py")),
    ("runtime-supervision", "Runtime Supervision", "The runtime substrate can supervise the generated app as a loopback uvicorn subprocess with local mock-only environment and persisted runtime state/events/logs.", ("factory/operator_portal/runtime_store.py", "factory/operator_portal/runtime_supervisor.py")),
    ("runtime-api", "Runtime API", "Runtime operations are exposed through portal API endpoints guarded by approval consumption and tested for rejection, replay prevention, catalog, and view behavior.", ("factory/operator_portal/runtime_api.py", "tests/phase50/test_runtime_api.py")),
    ("generated-app", "Generated App", "The tracked generated application is an implemented local FastAPI app with dispute routes, mock ecosystem action, audit/runtime plumbing, and automated API tests.", ("workspace/factory_generated/upi_dispute_resolution/generated_application/app/upi_dispute_app/main.py", "workspace/factory_generated/upi_dispute_resolution/generated_application/tests/test_api.py")),
    ("generated-app-settings", "Generated Settings", "The generated app enforces local/test environment, mock-only ecosystem, disabled live provider calls, no real secrets, and data-dir-contained persistence paths.", ("workspace/factory_generated/upi_dispute_resolution/generated_application/app/upi_dispute_app/settings.py",)),
    ("generated-persistence", "Generated Persistence", "The generated app persistence layer is standard-library SQLite with uniqueness-based idempotency/conflict support and JSON payload storage, not an external database or ORM.", ("workspace/factory_generated/upi_dispute_resolution/generated_application/app/upi_dispute_app/repository.py",)),
    ("domain-foundations", "Domain Foundation", "The failed-debit capability has a richer domain model and application service foundation than the generated FastAPI app alone, with automated tests for lifecycle and domain rules.", ("factory/application_engineering/failed_debit_capability.py", "tests/test_phase55_failed_debit_capability.py")),
    ("portfolio-contracts", "Portfolio Contracts", "The portfolio subsystem defines local-loopback mock-only policy and bounded local runtime quotas.", ("factory/application_engineering/portfolio.py",)),
    ("portal-ui", "Portal UI", "The browser UI is locally served and tested for key workflow controls and endpoint wiring.", ("factory/operator_portal/web_ui/app.py", "tests/test_phase49a_browser_driven_intake_orchestration.py")),
    ("GR-001", "Standing Policy", "The control plane implements a default-deny, fail-closed standing policy with explicit human-gated and prohibited actions.", ("config/control_plane/standing_policy.json", "tests/control_plane/test_manifest_policy_lifecycle.py", "tools/factory_control_plane/policy.py")),
    ("GR-002", "Manifest Validation", "Campaign manifests are parsed through strict deterministic validation before execution.", ("tests/control_plane/test_manifest_policy_lifecycle.py", "tools/factory_control_plane/manifest.py")),
    ("GR-003", "State Engine", "Control-plane state and evidence are persisted locally in SQLite with drift checks and event hashes.", ("tests/control_plane/test_state_engine_executor.py", "tools/factory_control_plane/state.py")),
    ("GR-004", "Evidence Envelope", "Control-plane evidence is locally envelope-based, hash-backed, and sealed for replay or review.", ("tests/control_plane/test_state_engine_executor.py", "tools/factory_control_plane/engine.py", "tools/factory_control_plane/evidence.py")),
    ("GR-005", "Workflow Evidence", "The Phase 9 workflow provides deterministic audit/checkpoint evidence but not interactive approval or true resume execution.", ("factory/workflows/state_machine.py", "tests/test_phase9_workflow_orchestration.py")),
    ("GR-006", "Repair Catalog", "Autonomous repair is catalog-driven, bounded, and fail-closed for unknown or unsafe repair conditions.", ("config/autonomous/repair_catalog.json", "config/autonomous/supervisor_limits.json", "tests/autonomous_supervisor/test_phase46l_declarative_repair_policy.py", "tools/autonomous_supervisor/policy.py")),
    ("GR-007", "Recovery Mechanics", "Supervisor recovery includes candidate-scope verification, runtime-noise normalization, prerequisite hydration, rollback-to-IMPLEMENTED, and resume under governed constraints.", ("config/autonomous/runtime_noise_policy.json", "tools/autonomous_supervisor/engine.py")),
    ("GR-008", "Generated Runtime Hardening", "The generated application is configured to fail closed outside local mock mode and explicitly disallows live providers, real secrets, production readiness, and certification claims.", ("tests/test_phase39_generated_application_runtime_hardening.py", "workspace/factory_generated/upi_dispute_resolution/generated_application/app/upi_dispute_app/runtime.py", "workspace/factory_generated/upi_dispute_resolution/generated_application/app/upi_dispute_app/settings.py")),
    ("GR-009", "Idempotent Intake", "The generated app implements local idempotent dispute intake, duplicate detection, UPI masking, and basic sensitive-number rejection.", ("workspace/factory_generated/upi_dispute_resolution/generated_application/app/upi_dispute_app/main.py", "workspace/factory_generated/upi_dispute_resolution/generated_application/app/upi_dispute_app/repository.py", "workspace/factory_generated/upi_dispute_resolution/generated_application/tests/test_api.py")),
    ("GR-010", "Local Audit Metrics", "The generated app has local JSONL audit logging and local runtime counters with explicit mock/certification boundaries.", ("tests/test_phase39_generated_application_runtime_hardening.py", "workspace/factory_generated/upi_dispute_resolution/generated_application/app/upi_dispute_app/audit.py", "workspace/factory_generated/upi_dispute_resolution/generated_application/app/upi_dispute_app/main.py")),
    ("GR-011", "Kernel Governance", "The factory contains a tested local application-engineering kernel for rollback, concurrency, idempotency, transactional outbox, tamper-evident audit, authorization, redacted logging, and metrics.", ("factory/application_engineering/local_platform_kernel.py", "tests/test_phase54_local_platform_kernel.py")),
    ("GR-012", "Capability Governance", "A deeper failed-debit capability has tested authorization, idempotency, optimistic concurrency, audit, and transition invariants, separate from the tracked generated FastAPI app.", ("factory/application_engineering/failed_debit_capability.py", "tests/test_phase55_failed_debit_capability.py")),
    ("GR-013", "Portfolio Approval", "Portfolio runtime management binds runtime ownership to immutable version identity and uses scoped one-time local approvals without persisting the raw token.", ("factory/application_engineering/portfolio.py", "tests/phase51/test_security_guards.py")),
    ("GR-014", "Supply Chain Non-Claim", "Supply-chain provenance support is local readiness evidence, not formal attestation, signing, publication, registry push, or certification.", ("policies/phase19_supply_chain_provenance_policy.json", "scripts/run_phase19_supply_chain_provenance_hardening.py", "tests/test_phase19_supply_chain_provenance_hardening.py")),
    ("GR-015", "Structured Logging", "Factory observability includes structured JSON logs with trace context and sensitive-key redaction.", ("factory/observability/structured_logging.py", "tests/test_phase54_local_platform_kernel.py")),
    ("GR-016", "Identity Migration", "Identity migration is governed by canonical identifiers, compatibility boundaries, human-gated alias retirement/renames, and hash-replay evidence.", ("config/identity/canonical_identity.json", "config/technical_identity_contract.json", "tests/transformation/test_phase46j_migration_evidence.py")),
    ("GR-017", "Baseline Governance", "Tracked governance evidence preserves baseline provenance and core project boundaries around mock ecosystem, official-claim evidence, mutation auditing, and blocker feedback.", ("factory/validators/validate_baseline_provenance.py", "factory_governance/05_POLICY_REGISTRY.yaml", "factory_governance/baseline_provenance_manifest.json")),
    ("GR-018", "Security Expectations", "Security and SBOM expectations exist as governance requirements, while executable evidence supports dependency inventory/provenance readiness rather than a formal SBOM claim.", ("factory_governance/14_SECURITY_AND_RED_TEAM_PLAYBOOK.md", "scripts/run_phase19_supply_chain_provenance_hardening.py")),
    ("portal-api-routes", "Portal API Routes", "The operator portal API is a FastAPI application that exposes local health, evidence, download, validation, browser-run, deep-engineering, runtime, portfolio, debug-plan, and documentation routes.", ("factory/operator_portal/local_web_api.py",)),
    ("browser-state-machine", "Browser State Machine", "Browser-driven application engineering uses an explicit state machine and rejects invalid state transitions.", ("factory/operator_portal/browser_intake_orchestration.py",)),
    ("browser-run-flow", "Browser Run Flow", "The browser portal enforces requirement validation, plan generation, explicit approval, and queued execution before application engineering can run.", ("factory/operator_portal/browser_intake_orchestration.py",)),
    ("execution-fail-closed", "Execution Fail Closed", "Application engineering execution fails closed: portfolio registration happens only after GO gates, otherwise the run transitions to FAILED.", ("factory/operator_portal/browser_intake_orchestration.py",)),
    ("generated-test-openapi-gates", "Generated Gates", "Generated tests and OpenAPI publication are material GO gates, and failing generated tests block application publication and portfolio registration.", ("factory/operator_portal/browser_intake_orchestration.py", "tests/test_portal_generated_tests_openapi_evidence.py")),
    ("validation-runner-allowlist", "Validation Runner Allowlist", "Portal-triggered validation is allowlist-based by command ID and rejects arbitrary shell text or extra shell fields.", ("factory/operator_portal/validation_runner.py", "tests/test_phase35_operator_portal_local_web_api.py")),
    ("runtime-approval-model", "Runtime Approval Model", "Direct runtime start/restart/stop are approval-gated with scoped one-time nonces and replay rejection.", ("factory/operator_portal/runtime_api.py", "factory/operator_portal/runtime_store.py", "tests/phase50/test_runtime_api.py")),
    ("runtime-state-machine", "Runtime State Machine", "Direct runtime lifecycle state transitions are explicitly constrained and invalid transitions fail closed.", ("factory/operator_portal/runtime_contracts.py", "tests/phase50/test_runtime_contracts.py")),
    ("runtime-process-lifecycle", "Runtime Process Lifecycle", "The runtime supervisor launches the generated FastAPI app locally under uvicorn, validates health, handles duplicate starts and stop cleanup, and rejects port collisions.", ("factory/operator_portal/runtime_supervisor.py", "tests/phase50/test_runtime_supervisor.py")),
    ("runtime-network-guardrails", "Runtime Network Guardrails", "Runtime OpenAPI/scenario HTTP access is constrained to loopback HTTP on the owned port with GET/POST only and explicit payload, response, time, and concurrency budgets.", ("factory/operator_portal/runtime_network_policy.py", "tests/phase50/test_runtime_network_policy.py", "tests/phase50/test_runtime_security.py")),
    ("runtime-openapi", "Runtime OpenAPI", "Runtime OpenAPI retrieval is implemented as a bounded loopback fetch from the generated FastAPI app and is tested end-to-end.", ("factory/operator_portal/runtime_api.py", "factory/operator_portal/runtime_openapi.py", "tests/phase50/test_runtime_openapi_scenarios_evidence.py")),
    ("runtime-scenarios", "Runtime Scenarios", "Runtime scenarios cover positive, negative, boundary, idempotency, resilience, security, timeout, and metrics contracts and produce a GO/NO_GO result.", ("factory/operator_portal/runtime_scenarios.py", "tests/phase50/test_runtime_openapi_scenarios_evidence.py", "tests/phase50/test_runtime_scenarios.py")),
    ("logs-metrics", "Logs And Metrics", "Portal runtime logs and metrics are local status/counter/identity surfaces, not production telemetry.", ("factory/operator_portal/portfolio_api.py", "factory/operator_portal/runtime_api.py", "tests/test_portal_generated_tests_openapi_evidence.py")),
    ("runtime-evidence", "Runtime Evidence", "Runtime evidence bundles include checksum inventories and validation gates, and require scenario results plus ordered events and no plaintext approval token for GO.", ("factory/operator_portal/runtime_evidence.py", "tests/phase50/test_runtime_evidence.py", "tests/phase50/test_runtime_openapi_scenarios_evidence.py")),
    ("browser-downloads", "Browser Downloads", "Generated application and evidence downloads are only available after a SUCCEEDED browser run and include checksums plus execution/OpenAPI evidence.", ("factory/operator_portal/browser_intake_orchestration.py", "factory/operator_portal/local_web_api.py")),
    ("generated-app-api", "Generated App API", "The tracked generated application is a real local FastAPI UPI dispute simulation API with tested health, dispute CRUD/read, idempotency, validation, masking, and mock ecosystem behavior.", ("workspace/factory_generated/upi_dispute_resolution/generated_application/app/upi_dispute_app/main.py", "workspace/factory_generated/upi_dispute_resolution/generated_application/tests/test_api.py")),
    ("generated-app-boundaries", "Generated App Boundaries", "The generated application enforces mock-only local runtime settings and uses local mock adapters rather than live payment ecosystem integrations.", ("workspace/factory_generated/upi_dispute_resolution/generated_application/README.md", "workspace/factory_generated/upi_dispute_resolution/generated_application/app/upi_dispute_app/mock_ecosystem.py", "workspace/factory_generated/upi_dispute_resolution/generated_application/app/upi_dispute_app/settings.py")),
    ("native-bootstrap", "Native Bootstrap", "The native bootstrap route is loopback-only and local-first, with dependency setup from requirements-recipient.txt and explicit mock/no-LLM environment defaults.", ("README.md", "run_factory.sh")),
    ("docker-route", "Docker Route", "The Docker route is implemented for a local operator portal container with loopback publication, non-root/read-only controls, persistent /app/.var state, health checks, and mock/no-LLM/no-real-payment environment enforcement.", ("Dockerfile", "compose.yaml", "scripts/run_docker_factory_portal.py", "tests/test_docker_platform_contract.py")),
    ("platform-boundary", "Platform Boundary", "Supported platform claims are conservative: native Ubuntu/Linux and Docker/Compose on Linux/macOS/Windows Docker Desktop, with no native Windows/macOS validation claim.", ("README.md", "config/supported_platforms.yaml", "tests/test_docker_platform_contract.py")),
    ("public-clone-readiness", "Public Clone Readiness", "Public clone readiness has a deterministic validator and automated tests for repository hygiene, dependency source policy, startup docs, state policy, OpenAPI/test hooks, secrets, filesystem modes, symlinks, large artifacts, and fail-closed behavior.", ("scripts/validate_public_clone_readiness.py", "tests/test_public_clone_readiness_validator.py")),
    ("deployment-nonclaims", "Deployment Non-Claims", "Deployment documentation preserves explicit non-claims around production, live payments, certification/approval, real data, and legal sufficiency.", ("README.md", "docs/deployment/DEPLOYMENT_BOUNDARIES_AND_NON_CLAIMS.md", "docs/deployment/FACTORY_LOCAL_DEPLOYMENT_GUIDE.md")),
)
LIMITATIONS_AND_NON_CLAIMS = (
    "External payment ecosystems remain mocked or simulated only; no real payment rails, bank, PSP, NPCI, RBI, settlement, customer, or live provider integrations are claimed.",
    "Runtime LLM use is disabled or zero by default; optional live routes require explicit gates and credentials and are not normal execution.",
    "Certification-ready-not-certified wording is a boundary statement, not evidence of regulatory approval, legal sufficiency, or production readiness.",
    "Portal validation accepts allowlisted command IDs only, not arbitrary shell text.",
    "Generated-app route-level authentication and authorization are not claimed for the tracked FastAPI app.",
    "Runtime metrics and logs are local counters/status metadata, not production observability or telemetry.",
    "Phase 66 memory is in-memory, run-scoped, and resettable; persistent long-term memory or cross-run learning is not claimed.",
    "Feedback capture is local or in-memory and does not prove production adaptive behavior.",
    "Autonomous repair is catalog-authorized, attempt-limited, deterministic, and fail-closed; arbitrary self-healing is not claimed.",
    "Supply-chain support is readiness and provenance evidence only; formal attestation, signing, registry publication, and certification are not claimed.",
    "Native platform support is conservative; native Windows and native macOS runtime validation are not claimed.",
    "Generated tests and OpenAPI publication are gates that require execution evidence; source presence alone is not a GO result.",
    "Secret and PII controls are local heuristics and fail-closed configuration checks, not full DLP or privacy certification.",
    "The Phase 9 workflow records review/resume metadata and deterministic evidence; it is not an interactive approval engine.",
    "Runtime supervision can start a local uvicorn subprocess when invoked; this guide generation does not start services.",
    "Docker support is a local operator portal route, not public hosting or production deployment.",
    "No repository artifact may claim RBI, NPCI, bank, PSP, ODR, payment-rail, legal, regulatory, PCI, ISO, SLSA, or production certification.",
    "Optional OpenAI and LangGraph code paths are boundary/readiness paths unless specifically gated and executed outside this offline guide build.",
    "The guide builder computes source hashes from the checked-out repository at build time and fails on missing tracked evidence.",
    "Repository evidence supports local deterministic operation and governed review boundaries, not live customer-dispute processing.",
)
REDUCED_MOTION_POLICY = {
    "css_media_query": "@media (prefers-reduced-motion: reduce)",
    "html_marker": "data-reduced-motion-policy",
    "behavior": "All CSS/SVG guide animations are disabled and smooth scrolling is removed when the user requests reduced motion.",
    "animated_classes": ["anim-request", "anim-gate", "anim-state", "anim-evidence", "anim-repair"],
}


@dataclass(frozen=True)
class Claim:
    id: str
    section: str
    title: str
    statement: str
    sources: tuple[dict[str, Any], ...]
    confidence: str
    workstream: str


@dataclass(frozen=True)
class SourceFactInventory:
    route_declarations: tuple[dict[str, str], ...]
    ui_controls: tuple[str, ...]


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _json_sha(value: Any) -> str:
    return _sha256_bytes(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def _source(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    if not path.is_file():
        raise ValueError(f"documentation source input missing: {relative}")
    return {"path": relative, "source_kind": "tracked_file", "sha256": _sha256_file(path), "size_bytes": path.stat().st_size}


def _tracked_files(root: Path) -> set[str]:
    import subprocess

    completed = subprocess.run(
        ["git", "-C", str(root), "ls-files"],
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise ValueError(f"cannot enumerate tracked documentation sources: {completed.stderr.strip()}")
    return {line.strip() for line in completed.stdout.splitlines() if line.strip()}


def _tracked_text(root: Path, tracked_files: set[str], relative: str) -> str:
    path = root / relative
    if relative not in tracked_files or not path.is_file():
        raise ValueError(f"documentation source fact input must be a tracked file: {relative}")
    return path.read_text(encoding="utf-8")


def _repository_source_fact_inventory(root: Path, tracked_files: set[str]) -> SourceFactInventory:
    route_source_paths = (
        "factory/operator_portal/local_web_api.py",
        "factory/operator_portal/runtime_api.py",
        "factory/operator_portal/portfolio_api.py",
        "factory/operator_portal/debug_plan_api.py",
        "factory/operator_portal/documentation_api.py",
    )
    route_pattern = re.compile(r"@(app|router)\.(get|post|put|patch|delete)\(\s*[\"']([^\"']+)[\"']")
    prefix_pattern = re.compile(r"router\s*=\s*APIRouter\([^)]*prefix\s*=\s*[\"']([^\"']+)[\"']", re.DOTALL)
    route_declarations: list[dict[str, str]] = []
    for relative in route_source_paths:
        text = _tracked_text(root, tracked_files, relative)
        prefix_match = prefix_pattern.search(text)
        router_prefix = prefix_match.group(1) if prefix_match else ""
        for match in route_pattern.finditer(text):
            raw_route = match.group(3)
            route = raw_route if match.group(1) == "app" else f"{router_prefix}{raw_route}"
            route_declarations.append(
                {
                    "method": match.group(2).upper(),
                    "route": route,
                    "source_path": relative,
                }
            )

    html = _tracked_text(root, tracked_files, "factory/operator_portal/web_ui/static/index.html")
    control_pattern = re.compile(r'data-(?:action|link)="([^"]+)"')
    ui_controls = tuple(sorted(set(control_pattern.findall(html))))
    route_declarations = sorted(route_declarations, key=lambda item: (item["route"], item["method"], item["source_path"]))
    if len(route_declarations) < 60:
        raise ValueError(f"tracked portal route declaration inventory is unexpectedly shallow: {len(route_declarations)}")
    if len(ui_controls) < 37:
        raise ValueError(f"tracked portal UI control inventory is unexpectedly shallow: {len(ui_controls)}")
    return SourceFactInventory(route_declarations=tuple(route_declarations), ui_controls=ui_controls)


def _validate_manifest_against_source_facts(
    ui_manifest: dict[str, Any],
    source_facts: SourceFactInventory,
) -> None:
    manifest_controls = {
        str(item.get("action") or item.get("link") or "")
        for item in _as_list(ui_manifest.get("controls"))
        if isinstance(item, dict)
    }
    source_controls = set(source_facts.ui_controls)
    missing_controls = sorted(manifest_controls - source_controls)
    if missing_controls:
        raise ValueError(f"UI manifest controls are not present in tracked UI source: {missing_controls}")

    source_route_pairs = {(item["method"], item["route"]) for item in source_facts.route_declarations}
    missing_routes = sorted(
        (str(item.get("method", "")), str(item.get("route", "")))
        for item in _as_list(ui_manifest.get("routes"))
        if isinstance(item, dict) and (str(item.get("method", "")), str(item.get("route", ""))) not in source_route_pairs
    )
    if missing_routes:
        raise ValueError(f"UI manifest routes are not present in tracked API source: {missing_routes}")


def _verified_source(root: Path, tracked_files: set[str], relative: str, *, locator: str, observation: str) -> dict[str, Any]:
    path = root / relative
    if relative not in tracked_files or not path.is_file():
        raise ValueError(f"documentation claim evidence must be a tracked file: {relative}")
    return {
        "path": relative,
        "source_kind": "tracked_file",
        "sha256": _sha256_file(path),
        "locator": locator,
        "observation": observation,
    }


def _safe_id(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip()).strip("-").lower()
    return cleaned or "item"


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _split_evidence_paths(raw_path: str) -> list[str]:
    candidates: list[str] = []
    for part in re.split(r";|,", raw_path):
        token = part.strip().strip("`")
        if not token:
            continue
        candidates.append(token)
    return candidates


def _source_for_observation(root: Path, report_path: Path, evidence: dict[str, Any]) -> dict[str, Any]:
    raw_path = str(evidence.get("path", "")).strip()
    locator = str(evidence.get("symbol_or_line", "")).strip() or "discovery observation"
    observation = str(evidence.get("observation", "")).strip()
    for candidate in _split_evidence_paths(raw_path):
        path = root / candidate
        if path.is_file():
            return {
                "path": candidate,
                "source_kind": "tracked_file",
                "sha256": _sha256_file(path),
                "locator": locator,
                "observation": observation,
            }
        if path.is_dir():
            raise ValueError(f"supplemental documentation evidence must resolve to tracked files, not directories: {candidate}")
    relative_report = report_path.relative_to(root).as_posix()
    return {
        "path": relative_report,
        "source_kind": "tracked_file",
        "sha256": _sha256_file(report_path),
        "locator": f"verified_claims evidence: {locator}",
        "observation": observation or raw_path,
    }


def _repository_claims(root: Path, tracked_files: set[str]) -> list[Claim]:
    claims: list[Claim] = []
    for claim_id, title, statement, paths in REPOSITORY_CLAIM_SPECS:
        section = _section_for_claim(claim_id, statement)
        sources = tuple(
            _verified_source(
                root,
                tracked_files,
                relative,
                locator=f"{title} tracked evidence",
                observation=f"Tracked source file supports claim {claim_id}: {statement}",
            )
            for relative in paths
        )
        claims.append(
            Claim(
                id=claim_id,
                section=section,
                title=title,
                statement=statement,
                sources=sources,
                confidence="HIGH",
                workstream="repository_native",
            )
        )
    seed_paths = sorted({path for _, _, _, paths in REPOSITORY_CLAIM_SPECS for path in paths})
    for index, relative in enumerate(seed_paths[:36], start=1):
        claim_id = f"source-inventory-{index:02d}"
        statement = f"Tracked repository source `{relative}` is included in the build-time documentation inventory with SHA-256 evidence."
        claims.append(
            Claim(
                id=claim_id,
                section="Repository architecture",
                title=f"Source Inventory {index:02d}",
                statement=statement,
                sources=(
                    _verified_source(
                        root,
                        tracked_files,
                        relative,
                        locator="build-time tracked file inventory",
                        observation=statement,
                    ),
                ),
                confidence="HIGH",
                workstream="repository_inventory",
            )
        )
    return claims


def _section_for_claim(claim_id: str, statement: str) -> str:
    for section, claim_ids in SECTION_CLAIMS.items():
        if claim_id in claim_ids:
            return section
    text = statement.lower()
    if "llm" in text or "openai" in text or "prompt" in text:
        return "LLM and prompt strategy"
    if "retrieval" in text or "embedding" in text:
        return "Knowledge retrieval"
    if "approval" in text or "state machine" in text:
        return "Operator portal lifecycle"
    if "sqlite" in text or "idempot" in text or "outbox" in text:
        return "Persistence and consistency"
    if "docker" in text or "platform" in text or "deployment" in text:
        return "Deployment and portability"
    if "repair" in text or "recovery" in text or "fail closed" in text:
        return "Failure modes and recovery"
    return "Executive technical summary"


def _load_discovery(root: Path, discovery_dir: Path | None) -> tuple[dict[str, Any], dict[str, dict[str, Any]], list[Claim]]:
    if discovery_dir is None:
        return {
            "status": "repository_native_claims",
            "unsupported_claims": [],
            "workstreams": {},
        }, {}, []
    elif discovery_dir.is_absolute():
        candidate = discovery_dir
    else:
        candidate = root / discovery_dir
    reports: dict[str, dict[str, Any]] = {}
    if candidate.is_dir():
        for filename in SUPPLEMENTAL_REPORT_FILENAMES:
            path = candidate / filename
            if not path.is_file():
                raise ValueError(f"missing supplemental discovery report: {path}")
            reports[filename] = _load_json(path)
    else:
        reports["discovery_summary.json"] = {
            "status": "supplemental_discovery_dir_missing",
            "total_verified_claims": 0,
            "unsupported_claims": [],
            "workstreams": {},
        }
    claims: list[Claim] = []
    for filename, report in sorted(reports.items()):
        if filename == "discovery_summary.json":
            continue
        report_path = candidate / filename
        workstream = str(report.get("workstream") or filename.removesuffix(".json"))
        for item in _as_list(report.get("verified_claims")):
            if not isinstance(item, dict):
                continue
            claim_id = str(item.get("id") or _safe_id(str(item.get("title", "claim"))))
            statement = str(item.get("statement", "")).strip()
            if not statement:
                raise ValueError(f"empty statement for discovery claim {claim_id}")
            section = _section_for_claim(claim_id, statement)
            sources = tuple(
                _source_for_observation(root, report_path, evidence)
                for evidence in _as_list(item.get("evidence"))
                if isinstance(evidence, dict)
            )
            if not sources:
                sources = (
                    {
                        "path": report_path.relative_to(root).as_posix(),
                        "sha256": _sha256_file(report_path),
                        "locator": f"verified_claims[{claim_id}]",
                        "observation": "Claim supplied by supplemental discovery report.",
                    },
                )
            claims.append(
                Claim(
                    id=claim_id,
                    section=section,
                    title=str(item.get("title") or claim_id),
                    statement=statement,
                    sources=sources,
                    confidence=str(item.get("confidence") or "UNSPECIFIED"),
                    workstream=workstream,
                )
            )
    summary = reports.get("discovery_summary.json", {})
    return summary, reports, claims


def _claim_map(claims: Iterable[Claim]) -> dict[str, Claim]:
    result: dict[str, Claim] = {}
    for claim in claims:
        result.setdefault(claim.id, claim)
    return result


def _claim_text(claims_by_id: dict[str, Claim], claim_id: str) -> str:
    claim = claims_by_id.get(claim_id)
    if claim:
        return claim.statement
    return f"Claim {claim_id} is reserved for source traceability."


def _p(claim_id: str, text: str) -> str:
    return f'<p data-claim-id="{escape(claim_id)}">{escape(text)}</p>'


def _li(claim_id: str, text: str) -> str:
    return f'<li data-claim-id="{escape(claim_id)}">{escape(text)}</li>'


def _claim_list(claims_by_id: dict[str, Claim], claim_ids: Iterable[str], limit: int = 5) -> str:
    items = []
    for claim_id in claim_ids:
        if claim_id in claims_by_id:
            items.append(_li(claim_id, claims_by_id[claim_id].statement))
        if len(items) >= limit:
            break
    return "<ul>" + "".join(items) + "</ul>"


def _details(title: str, body: str) -> str:
    return f"<details><summary>{escape(title)}</summary>{body}</details>"


def _table(headers: list[str], rows: list[list[str]]) -> str:
    head = "".join(f"<th>{escape(header)}</th>" for header in headers)
    body = "".join("<tr>" + "".join(f"<td>{escape(cell)}</td>" for cell in row) + "</tr>" for row in rows)
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def _claim_evidence_detail(claims: Iterable[Claim]) -> str:
    head = "".join(f"<th>{escape(header)}</th>" for header in ["Claim", "Section", "Statement", "Tracked evidence files"])
    body_rows: list[str] = []
    for claim in sorted(claims, key=lambda item: (item.section, item.id)):
        source_paths = ", ".join(str(source["path"]) for source in claim.sources)
        cells = "".join(
            f"<td>{escape(cell)}</td>"
            for cell in [claim.id, claim.section, claim.statement, source_paths]
        )
        body_rows.append(f'<tr data-claim-id="{escape(claim.id)}">{cells}</tr>')
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body_rows)}</tbody></table>"


def _diagram_svg(diagram_id: str, title: str, desc: str, nodes: list[str], claim_ids: tuple[str, ...], animated_class: str) -> str:
    svg_id = _safe_id(diagram_id)
    title_id = f"{svg_id}-title"
    desc_id = f"{svg_id}-desc"
    width = 960
    node_width = max(112, min(172, (width - 70) // max(1, len(nodes)) - 14))
    gap = (width - 50 - node_width) // max(1, len(nodes) - 1) if len(nodes) > 1 else 0
    node_markup: list[str] = []
    edge_markup: list[str] = []
    for index, node in enumerate(nodes):
        x = 25 + index * gap
        node_markup.append(
            f'<g class="diagram-node"><rect x="{x}" y="44" width="{node_width}" height="64" rx="8"/>'
            f'<text x="{x + 14}" y="80">{escape(node)}</text></g>'
        )
        if index:
            previous_x = 25 + (index - 1) * gap + node_width + 8
            edge_markup.append(
                f'<path class="diagram-edge {escape(animated_class)}" d="M{previous_x} 76 H{x - 10}" '
                f'marker-end="url(#{svg_id}-arrow)"/>'
            )
    return (
        f'<figure class="diagram" data-diagram-id="{escape(diagram_id)}" data-claim-id="{escape(claim_ids[0])}">'
        f'<svg role="img" viewBox="0 0 {width} 154" aria-labelledby="{title_id} {desc_id}" xmlns="http://www.w3.org/2000/svg">'
        f'<title id="{title_id}">{escape(title)}</title><desc id="{desc_id}">{escape(desc)}</desc>'
        f'<defs><marker id="{svg_id}-arrow" markerWidth="9" markerHeight="9" refX="8" refY="4" orient="auto">'
        '<path d="M0,0 L0,8 L9,4 z"/></marker></defs>'
        f'<text class="diagram-title" x="25" y="24">{escape(title)}</text>'
        f'{"".join(edge_markup)}{"".join(node_markup)}</svg>'
        f'<figcaption>{escape(desc)} Source claims: {escape(", ".join(claim_ids))}.</figcaption></figure>'
    )


def _css() -> str:
    return """
:root{--ink:#15212a;--muted:#53606b;--paper:#fbfcfd;--band:#eef4f1;--line:#c7d1d8;--accent:#0f766e;--accent2:#8a4b0f;--gate:#7c2d12;--ok:#166534}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--paper);color:var(--ink);font-family:Arial,Helvetica,sans-serif;line-height:1.48}
a{color:#0f5f8f}header{background:#183238;color:white;padding:28px 34px 24px}header p{max-width:980px;margin:8px 0 0;color:#dce9e8}
nav{position:sticky;top:0;z-index:2;background:white;border-bottom:1px solid var(--line);padding:10px 24px}nav ul{display:flex;flex-wrap:wrap;gap:8px;margin:0;padding:0;list-style:none}nav a{display:block;padding:6px 9px;border:1px solid var(--line);border-radius:6px;text-decoration:none;color:var(--ink);font-size:13px;background:#fff}
main{max-width:1180px;margin:0 auto;padding:18px 24px 40px}section{padding:24px 0;border-bottom:1px solid var(--line)}h1,h2,h3{margin:0 0 12px;line-height:1.18}h1{font-size:32px}h2{font-size:24px}h3{font-size:17px;color:#253641}
.inventory{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:16px 0}.metric{background:white;border:1px solid var(--line);border-radius:8px;padding:12px}.metric strong{display:block;font-size:24px;color:var(--accent)}
.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.panel{background:white;border:1px solid var(--line);border-radius:8px;padding:14px}
ul{padding-left:22px}li{margin:6px 0}code{background:#edf2f4;border:1px solid #d8e0e5;border-radius:4px;padding:1px 4px}
details{background:white;border:1px solid var(--line);border-radius:8px;margin:10px 0;padding:10px 12px}summary{cursor:pointer;font-weight:700}
table{border-collapse:collapse;width:100%;background:white;margin:12px 0;font-size:13px}th,td{border:1px solid var(--line);padding:7px;text-align:left;vertical-align:top}th{background:#eaf1f1}
.diagram{margin:14px 0;background:white;border:1px solid var(--line);border-radius:8px;padding:10px;break-inside:avoid}.diagram svg{display:block;width:100%;height:auto}.diagram figcaption{color:var(--muted);font-size:13px;margin-top:6px}
svg rect{fill:#e9f3ef;stroke:#23635d;stroke-width:1.5}svg text{fill:var(--ink);font-size:13px}svg .diagram-title{font-size:15px;font-weight:700}svg .diagram-edge{fill:none;stroke:#23635d;stroke-width:2.5;stroke-linecap:round}
@keyframes request-flow-pulse{0%,100%{stroke-width:2.2;opacity:.58}50%{stroke-width:4;opacity:1}}
@keyframes approval-gate-swing{0%,100%{transform:translateY(0)}50%{transform:translateY(-3px)}}
@keyframes state-transition-step{0%{stroke-dashoffset:42}100%{stroke-dashoffset:0}}
@keyframes evidence-propagation-dash{0%{stroke-dashoffset:54}100%{stroke-dashoffset:0}}
@keyframes recovery-loop-rotate{0%{stroke-dashoffset:78}100%{stroke-dashoffset:0}}
.anim-request{animation:request-flow-pulse 2.2s ease-in-out infinite}.anim-gate{animation:approval-gate-swing 2.4s ease-in-out infinite}.anim-state{stroke-dasharray:12 8;animation:state-transition-step 2.8s linear infinite}.anim-evidence{stroke-dasharray:8 7;animation:evidence-propagation-dash 2.5s linear infinite}.anim-repair{stroke-dasharray:10 6;animation:recovery-loop-rotate 3s linear infinite}
@media (max-width:760px){header{padding:22px 18px}main{padding:12px 14px}.inventory,.grid{grid-template-columns:1fr}nav{position:static;padding:8px 12px}table{font-size:12px;display:block;overflow-x:auto}h1{font-size:27px}h2{font-size:21px}}
@media print{nav{display:none}body{background:white;color:black}main{max-width:none}.panel,.metric,details,.diagram{border-color:#999;box-shadow:none}section{break-inside:avoid}a{color:black;text-decoration:none}}
/* reduced-motion: static guide animations must respect user motion preferences. */
@media (prefers-reduced-motion: reduce){html{scroll-behavior:auto}.anim-request,.anim-gate,.anim-state,.anim-evidence,.anim-repair{animation:none!important;transition:none!important}}
"""


def _material_section(section: str, claims_by_id: dict[str, Claim], extra: str = "") -> str:
    claim_ids = SECTION_CLAIMS[section]
    claim_markup = _claim_list(claims_by_id, claim_ids)
    return (
        f'<section id="{_safe_id(section)}"><h2>{escape(section)}</h2>'
        f"{extra}{claim_markup}"
        f"{_details('Source-backed claim detail', _claim_list(claims_by_id, claim_ids, limit=12))}</section>"
    )


def _build_diagrams() -> list[dict[str, Any]]:
    return [
        {
            "id": "system-context",
            "title": "System Context",
            "purpose": "Shows operator, portal, local workspace, generated app, and evidence boundary.",
            "nodes": ["Operator", "Portal UI", "FastAPI API", "Workspace", "Generated App", "Evidence"],
            "source_claim_ids": ("startup-routes", "portal-api-routes", "generated-app-api"),
            "animated_class": "anim-request",
        },
        {
            "id": "runtime-topology",
            "title": "Runtime Topology",
            "purpose": "Shows approval-gated loopback runtime supervision and state capture.",
            "nodes": ["Approval", "Runtime API", "Supervisor", "Uvicorn", "Health", "State Store"],
            "source_claim_ids": ("runtime-api", "runtime-supervision", "runtime-evidence"),
            "animated_class": "anim-gate",
        },
        {
            "id": "requirements-compilation",
            "title": "Requirements Compilation",
            "purpose": "Shows deterministic Markdown normalization, diagnostics, traceability, and hash output.",
            "nodes": ["Markdown", "Sections", "Diagnostics", "IR", "Trace Rows", "Hash"],
            "source_claim_ids": ("requirements-ir", "requirements-fail-closed", "deep-composer"),
            "animated_class": "anim-evidence",
        },
        {
            "id": "approval-state-machine",
            "title": "Approval State Machine",
            "purpose": "Shows browser run transitions from accepted requirements to terminal result.",
            "nodes": ["Accepted", "Plan", "Approval", "Queued", "Validating", "Terminal"],
            "source_claim_ids": ("browser-state-machine", "browser-run-flow", "execution-fail-closed"),
            "animated_class": "anim-state",
        },
        {
            "id": "generated-app-flow",
            "title": "Generated App Request Flow",
            "purpose": "Shows request validation, masking, persistence, audit, and mock adapter action.",
            "nodes": ["Request", "Validate", "Mask", "SQLite", "Audit", "Mock Action"],
            "source_claim_ids": ("generated-app-api", "GR-009", "GR-010"),
            "animated_class": "anim-request",
        },
        {
            "id": "evidence-propagation",
            "title": "Evidence Propagation",
            "purpose": "Shows hashes and bundles moving from source through tests, OpenAPI, runtime, and manifest.",
            "nodes": ["Source", "Tests", "OpenAPI", "Runtime", "Bundle", "Manifest"],
            "source_claim_ids": ("generated-test-openapi-gates", "runtime-evidence", "GR-004"),
            "animated_class": "anim-evidence",
        },
        {
            "id": "tool-safeguards",
            "title": "Tool Safeguards",
            "purpose": "Shows deny-by-default policy, allowlisted commands, routing, and human review.",
            "nodes": ["Intent", "Policy", "Allowlist", "Approval", "Execute", "Report"],
            "source_claim_ids": ("GR-001", "validation-runner-allowlist", "C19"),
            "animated_class": "anim-gate",
        },
        {
            "id": "repair-loop",
            "title": "Repair And Recovery Loop",
            "purpose": "Shows bounded repair catalog handling and fail-closed recovery behavior.",
            "nodes": ["Failure", "Classify", "Catalog", "Scope", "Repair", "Resume"],
            "source_claim_ids": ("GR-006", "GR-007", "C23"),
            "animated_class": "anim-repair",
        },
    ]


def _collect_source_paths(root: Path, claims: list[Claim], discovery_reports: dict[str, dict[str, Any]]) -> list[str]:
    paths = set(LEGACY_SOURCE_PATHS)
    for claim in claims:
        for source in claim.sources:
            path = str(source["path"])
            if (root / path).is_file():
                paths.add(path)
    return sorted(paths)


def _technical_inventory(
    tracked_files: set[str],
    ui_manifest: dict[str, Any],
    debug_plan: dict[str, Any],
    claims: list[Claim],
    source_files: list[dict[str, Any]],
    source_facts: SourceFactInventory,
) -> dict[str, Any]:
    python_files = [path for path in tracked_files if path.endswith(".py")]
    prompt_files = [path for path in tracked_files if path.endswith(".md") and "prompt" in path.lower()]
    test_files = [
        path
        for path in tracked_files
        if path.startswith("tests/") and PurePosixPath(path).name.startswith("test_") and path.endswith(".py")
    ]
    return {
        "controls_traced": len(_as_list(ui_manifest.get("controls"))),
        "routes_traced": len(_as_list(ui_manifest.get("routes"))),
        "debug_plan_source_files": len(_as_list(debug_plan.get("source_files"))),
        "verified_claims_ingested": len(claims),
        "source_files_traced": len(source_files),
        "repository_python_files": len(python_files),
        "repository_test_files": len(test_files),
        "prompt_markdown_files": len(prompt_files),
        "source_route_declarations": len(source_facts.route_declarations),
        "source_ui_controls": len(source_facts.ui_controls),
        "required_topics": len(REQUIRED_TOPICS),
    }


def build_documentation(
    root: Path,
    ui_manifest: dict[str, Any],
    debug_plan: dict[str, Any],
    *,
    discovery_dir: Path | None = None,
) -> tuple[str, dict[str, Any]]:
    controls = _as_list(ui_manifest.get("controls"))
    routes = _as_list(ui_manifest.get("routes"))
    if not controls or not routes:
        raise ValueError("UI manifest must expose controls and routes")
    if not _as_list(debug_plan.get("source_files")):
        raise ValueError("debug plan must expose source files")

    tracked_files = _tracked_files(root)
    source_facts = _repository_source_fact_inventory(root, tracked_files)
    _validate_manifest_against_source_facts(ui_manifest, source_facts)
    discovery_summary, discovery_reports, supplemental_claims = _load_discovery(root, discovery_dir)
    claims = _repository_claims(root, tracked_files)
    for claim in supplemental_claims:
        eligible_sources = []
        for source in claim.sources:
            relative = str(source["path"])
            if relative in tracked_files and (root / relative).is_file():
                eligible_sources.append(source)
        if eligible_sources and claim.id not in {item.id for item in claims}:
            claims.append(
                Claim(
                    id=claim.id,
                    section=claim.section,
                    title=claim.title,
                    statement=claim.statement,
                    sources=tuple(eligible_sources),
                    confidence=claim.confidence,
                    workstream=claim.workstream,
                )
            )
    for claim in claims:
        for source in claim.sources:
            relative = str(source.get("path", ""))
            if source.get("source_kind") != "tracked_file" or relative not in tracked_files or not (root / relative).is_file():
                raise ValueError(f"documentation claim evidence must use tracked_file sources only: {relative}")
    claims_by_id = _claim_map(claims)
    source_paths = _collect_source_paths(root, claims, discovery_reports)
    source_files = [_source(root, path) for path in source_paths]
    diagrams = _build_diagrams()
    claim_evidence = [
        {
            "claim_id": claim.id,
            "section": claim.section,
            "statement": claim.statement,
            "sources": list(claim.sources),
        }
        for claim in claims
    ]
    unsupported_claims = sorted(
        {
            str(item)
            for report in discovery_reports.values()
            for item in _as_list(report.get("unsupported_claims"))
        }
    )
    limitations = sorted(
        set(LIMITATIONS_AND_NON_CLAIMS)
        | {
            str(item)
            for report in discovery_reports.values()
            for item in _as_list(report.get("limitations"))
        }
    )
    truth_boundaries = [
        "Local-first and deterministic-first operation is the documented boundary.",
        "External payment ecosystems remain mocked or simulated.",
        "Runtime LLM use is disabled or zero by default; optional live routes require explicit gates.",
        "Certification-ready-not-certified wording is allowed; certification, approval, production readiness, and legal sufficiency are non-claims.",
        "Portal actions use scoped approvals, state transitions, fixed command IDs, and local evidence.",
    ]
    technical_inventory = _technical_inventory(tracked_files, ui_manifest, debug_plan, claims, source_files, source_facts)

    route_rows = [
        [str(item.get("method", "")), str(item.get("route", ""))]
        for item in routes
        if isinstance(item, dict)
    ]
    control_rows = [
        [
            str(item.get("id", "")),
            str(item.get("action") or item.get("link") or ""),
            str(item.get("contract", {}).get("method", "")) if isinstance(item.get("contract"), dict) else "",
            str(item.get("contract", {}).get("route", "")) if isinstance(item.get("contract"), dict) else "",
        ]
        for item in controls
        if isinstance(item, dict)
    ]
    metrics = "".join(
        f'<div class="metric" data-claim-id="technical-inventory"><strong>{value}</strong>{escape(key.replace("_", " ").title())}</div>'
        for key, value in technical_inventory.items()
    )
    nav = "".join(f'<li><a href="#{_safe_id(topic)}">{escape(topic)}</a></li>' for topic in REQUIRED_TOPICS)
    diagram_markup = "".join(
        _diagram_svg(
            item["id"],
            item["title"],
            item["purpose"],
            item["nodes"],
            item["source_claim_ids"],
            item["animated_class"],
        )
        for item in diagrams
    )
    sections = [
        '<section id="executive-technical-summary"><h2>Executive technical summary</h2>'
        + _p("technical-inventory", "This guide is generated offline from tracked repository source, the operator UI manifest, and the factory debug plan.")
        + f'<div class="inventory">{metrics}</div>'
        + _claim_list(claims_by_id, SECTION_CLAIMS["Executive technical summary"])
        + "</section>",
        '<section id="truth-and-trust-boundaries"><h2>Truth and trust boundaries</h2>'
        + "<ul>"
        + "".join(_li("portal-boundaries", item) for item in truth_boundaries)
        + "</ul>"
        + _details("Unsupported claims removed from the guide", "<ul>" + "".join(_li("unsupported-claim", item) for item in unsupported_claims[:40]) + "</ul>")
        + "</section>",
        f'<section id="system-context"><h2>System context</h2>{diagram_markup}'
        + _claim_list(claims_by_id, SECTION_CLAIMS["System context"])
        + "</section>",
    ]
    for topic in REQUIRED_TOPICS[3:-2]:
        extra = ""
        if topic == "Operator portal lifecycle":
            extra = _details("Operator controls", _table(["Control", "Action", "Method", "Route"], control_rows))
        elif topic == "Testing and quality gates":
            extra = _details("Route inventory", _table(["Method", "Route"], route_rows))
        sections.append(_material_section(topic, claims_by_id, extra=extra))
    sections.append(
        '<section id="limitations-and-non-claims"><h2>Limitations and non-claims</h2>'
        + "<ul>"
        + "".join(_li("limitation", item) for item in limitations[:48])
        + "</ul></section>"
    )
    source_rows = [[item["path"], item["sha256"], str(item["size_bytes"])] for item in source_files]
    sections.append(
        '<section id="source-traceability"><h2>Source traceability</h2>'
        + _p("source-traceability", "Every manifest source file records path, SHA-256, and byte size. Claim evidence records path, SHA-256, locator, and observation.")
        + _claim_list(claims_by_id, SECTION_CLAIMS["Source traceability"], limit=12)
        + _details("Claim evidence", _claim_evidence_detail(claims))
        + _details("Source files", _table(["Path", "SHA-256", "Size"], source_rows))
        + "</section>"
    )

    html = (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        "<title>UPI App Factory Complete Guide</title><style>"
        + _css()
        + '</style></head><body data-reduced-motion-policy="prefers-reduced-motion: reduce disables guide animation">'
        + "<header><h1>UPI App Factory Complete Guide</h1>"
        + _p("commit-identity", "Technical guide refresh for the local governed UPI App Factory implementation at the requested baseline.")
        + "</header><nav aria-label=\"Guide sections\"><ul>"
        + nav
        + "</ul></nav><main>"
        + "".join(sections)
        + "</main></body></html>\n"
    )

    animations = [
        {
            "id": "request-flow-pulse",
            "purpose": "Animate local request and generated-app data flow.",
            "mechanism": "CSS keyframes vary SVG edge stroke width and opacity.",
            "reduced_motion": "disabled by prefers-reduced-motion: reduce",
            "source_claim_ids": ["portal-api-routes", "generated-app-api"],
        },
        {
            "id": "approval-gate-swing",
            "purpose": "Animate approval-gated control points.",
            "mechanism": "CSS keyframes translate gate-linked SVG edges.",
            "reduced_motion": "disabled by prefers-reduced-motion: reduce",
            "source_claim_ids": ["browser-run-flow", "runtime-api"],
        },
        {
            "id": "state-transition-step",
            "purpose": "Animate explicit state transitions.",
            "mechanism": "CSS keyframes move dash offsets along transition edges.",
            "reduced_motion": "disabled by prefers-reduced-motion: reduce",
            "source_claim_ids": ["browser-state-machine", "runtime-contracts"],
        },
        {
            "id": "evidence-propagation-dash",
            "purpose": "Animate evidence and hash propagation.",
            "mechanism": "CSS keyframes move dashed SVG strokes.",
            "reduced_motion": "disabled by prefers-reduced-motion: reduce",
            "source_claim_ids": ["GR-004", "runtime-evidence"],
        },
        {
            "id": "recovery-loop-rotate",
            "purpose": "Animate bounded repair and recovery loops.",
            "mechanism": "CSS keyframes cycle dash offsets on repair-flow edges.",
            "reduced_motion": "disabled by prefers-reduced-motion: reduce",
            "source_claim_ids": ["GR-006", "GR-007", "C23"],
        },
    ]
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": DETERMINISTIC_GENERATED_AT_UTC,
        "html_sha256": _sha256_bytes(html.encode("utf-8")),
        "source_files": source_files,
        "source_traceability": source_files,
        "technical_inventory": technical_inventory,
        "source_fact_inventory": {
            "route_declarations": list(source_facts.route_declarations),
            "ui_controls": list(source_facts.ui_controls),
        },
        "reduced_motion_policy": REDUCED_MOTION_POLICY,
        "animations": animations,
        "diagrams": [
            {
                "id": item["id"],
                "title": item["title"],
                "purpose": item["purpose"],
                "source_claim_ids": list(item["source_claim_ids"]),
            }
            for item in diagrams
        ],
        "claim_evidence": claim_evidence,
        "unresolved_claims": [],
        "truth_boundaries": truth_boundaries,
        "limitations": limitations,
        "ui_manifest_sha256": _json_sha(ui_manifest),
        "debug_plan_sha256": debug_plan.get("plan_sha256") or _json_sha(debug_plan),
        "discovery_summary_sha256": _json_sha(discovery_summary),
        "controls_traced": len(controls),
        "routes_traced": len(routes),
    }
    return html, manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--ui-manifest", type=Path, required=True)
    parser.add_argument("--debug-plan", type=Path, required=True)
    parser.add_argument("--html-out", type=Path, required=True)
    parser.add_argument("--manifest-out", type=Path, required=True)
    parser.add_argument("--discovery-dir", type=Path)
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    html, manifest = build_documentation(
        root,
        _load_json(args.ui_manifest),
        _load_json(args.debug_plan),
        discovery_dir=args.discovery_dir,
    )
    args.html_out.parent.mkdir(parents=True, exist_ok=True)
    args.manifest_out.parent.mkdir(parents=True, exist_ok=True)
    args.html_out.write_text(html, encoding="utf-8")
    args.manifest_out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
