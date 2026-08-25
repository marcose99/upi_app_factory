from __future__ import annotations

from factory.application_engineering.architecture_adapters import ArchitectureAdapter


def test_event_driven_overlay_composes_injected_service_and_unique_outbox() -> None:
    files = ArchitectureAdapter(
        "EVENT_DRIVEN_MODULAR_MONOLITH_OUTBOX", "test-adapter"
    ).render("APP-001")

    service_test = files["tests/test_service.py"]
    runtime_adapter = files["app/APP-001/infrastructure/runtime_adapters.py"]

    assert "DisputeApplicationService(adapters.case_repository, adapters.transactional_outbox)" in service_test
    assert "idempotency_key TEXT NOT NULL UNIQUE" in runtime_adapter
    assert "SELECT 1 FROM outbox WHERE idempotency_key=?" in runtime_adapter


def test_non_event_overlay_keeps_no_argument_service_composition() -> None:
    files = ArchitectureAdapter(
        "MODULAR_MONOLITH_HEXAGONAL", "test-adapter"
    ).render("APP-001")

    assert "service = DisputeApplicationService()" in files["tests/test_service.py"]


def test_adapter_does_not_overwrite_shared_executable_api_test() -> None:
    files = ArchitectureAdapter(
        "WORKFLOW_CENTRIC_MODULAR_MONOLITH", "workflow-test-isolation"
    ).render("sample_app")

    assert "tests/test_api_contract.py" not in files
    assert "tests/test_architecture_api_contract.py" in files
