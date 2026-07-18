.PHONY: setup validate validate-governance test lint type run release-pack phase43-demo-reviewer-pack phase59-60-deep-engineering-closure

setup:
	python3 -m venv .venv
	. .venv/bin/activate && python -m pip install --upgrade pip
	. .venv/bin/activate && pip install -e ".[dev]"

lint:
	ruff check app factory tests

type:
	mypy app factory

test:
	pytest

validate-governance:
	python -m factory.validators.validate_governance_pack
	python -m factory.validators.validate_policy_registry
	python -m factory.validators.validate_mock_boundaries
	python -m factory.validators.validate_evidence_ledger

validate: lint type test validate-governance
	python -m factory.validators.validate_release_readiness

run:
	uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

release-pack:
	python -m factory.release_pack.generate

phase43-demo-reviewer-pack:
	python scripts/run_phase43_one_command_demo_reviewer_pack.py

phase59-60-deep-engineering-closure:
	python scripts/run_phase59_60_deep_engineering_closure.py

validate-phase1:
	python -m factory.validators.validate_phase1_foundation

validate-combined-phases:
	python -m factory.validators.validate_phase2_to_phase5_combined
	$(MAKE) validate

validate-regeneration:
	python -m factory.validators.validate_regeneration_readiness

regenerate-mock-dispute-app:
	./scripts/regenerate_mock_dispute_app.sh

validate-baseline-provenance:
	python -m factory.validators.validate_baseline_provenance

.PHONY: run-governed-factory-run validate-factory-run
run-governed-factory-run:
	RUN_ID=$${RUN_ID:-manual_factory_run} python scripts/run_governed_factory_run.py --force

validate-factory-run:
	python scripts/validate_factory_run_manifest.py --latest

.PHONY: validate-debugging-standards
validate-debugging-standards:
	python scripts/validate_project_debugging_standards.py

.PHONY: validate-agent-prompts
validate-agent-prompts:
	python scripts/validate_agent_prompts.py

validate-agent-run:
	python scripts/validate_multi_agent_run.py --latest

run-multi-agent-simulation:
	python scripts/run_multi_agent_factory_simulation.py --run-id manual_agent_run --force

.PHONY: run-governed-workflow
run-governed-workflow:
	python scripts/run_governed_workflow.py --run-id phase9_manual_workflow --force

.PHONY: validate-workflow-run
validate-workflow-run:
	python scripts/validate_workflow_run.py --latest

validate-quality-dimensions:
	python scripts/validate_quality_dimensions.py


validate-generated-application-quality-prompting:
	python scripts/validate_generated_application_quality_prompting.py

validate-regulatory-governance:
	python scripts/validate_regulatory_governance.py
