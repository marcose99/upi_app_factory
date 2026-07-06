# UPI Dispute Resolution Factory Release Handoff Bundle

Phase: Phase 13J
Baseline tag: `v0.13.8-release-readiness-operator-acceptance`

## Purpose
This bundle gives another local operator the minimum deterministic handoff surface needed to inspect, validate, and run the governed factory.

## Operator commands
- `./factoryctl status`
- `./factoryctl adapters`
- `./factoryctl validate --quick`
- `./factoryctl validate`
- `./factoryctl portals`
- `./factoryctl handover`
- `./factoryctl logs`

## Truth boundary
This handoff bundle describes a locally runnable, deterministic governed factory release. Local deterministic execution remains the default. LangGraph/OpenAI execution remains detected and policy-gated, not falsely claimed as active.

## Required release files
- `README.md`
- `factoryctl`
- `scripts/factory_cli.py`
- `docs/phase13d/agent_adapter_execution_layer.md`
- `docs/phase13e/factory_cli_operator_surface.md`
- `docs/phase13f/operator_handover_closure.md`
- `docs/phase13g/readonly_validation_drift_guardrails.md`
- `docs/phase13h/release_state_lineage_registry.md`
- `docs/phase13i/release_readiness_operator_acceptance.md`
- `scripts/validate_phase13d_agent_adapter_execution.py`
- `scripts/validate_phase13e_factory_cli_operator_surface.py`
- `scripts/validate_phase13f_operator_handover_closure.py`
- `scripts/validate_phase13g_readonly_validation_guardrails.py`
- `scripts/validate_phase13h_release_state_lineage.py`
- `scripts/validate_phase13i_release_readiness.py`

## Validation
Run `python scripts/validate_phase13j_release_handoff_bundle.py` from the repository root.
