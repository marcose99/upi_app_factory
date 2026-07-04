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
