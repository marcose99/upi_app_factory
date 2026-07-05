.PHONY: setup validate validate-governance test lint type run release-pack

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
