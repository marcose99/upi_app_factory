from __future__ import annotations

from factory.operator_portal.runtime_openapi import RuntimeOpenAPIService


def test_openapi_service_is_importable() -> None:
    assert RuntimeOpenAPIService().__class__.__name__ == "RuntimeOpenAPIService"
