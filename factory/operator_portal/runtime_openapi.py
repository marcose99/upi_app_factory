from __future__ import annotations

import json
from typing import Any, cast
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError

from factory.operator_portal.runtime_contracts import (
    APP_ID,
    GENERATED_APPLICATION_VERSION,
    RuntimeContractError,
    sha256_bytes,
)
from factory.operator_portal.runtime_network_policy import MAX_RESPONSE_BYTES, normalize_runtime_url


class RuntimeOpenAPIService:
    def fetch(self, *, base_url: str, owned_port: int, manifest_sha256: str) -> dict[str, Any]:
        expected_identity = {
            "app_slug": APP_ID,
            "application_version": GENERATED_APPLICATION_VERSION,
            "manifest_sha256": manifest_sha256,
        }
        health = self._fetch_object(
            base_url=base_url,
            owned_port=owned_port,
            endpoint="/health",
            label="runtime health",
        )
        if health.get("status") != "ok" or any(
            health.get(key) != value
            for key, value in expected_identity.items()
        ):
            raise RuntimeContractError("runtime identity did not match OpenAPI attribution")
        payload = self._fetch_object(
            base_url=base_url,
            owned_port=owned_port,
            endpoint="/openapi.json",
            label="OpenAPI",
        )
        paths = payload.get("paths")
        if not isinstance(paths, dict):
            raise RuntimeContractError("OpenAPI paths are missing")
        inventory = []
        for path, methods in sorted(paths.items()):
            if not isinstance(path, str) or not path.startswith("/"):
                raise RuntimeContractError("OpenAPI path is unsafe")
            if isinstance(methods, dict):
                for method in sorted(methods):
                    if method.upper() in {"GET", "POST"}:
                        inventory.append({"method": method.upper(), "path": path})
        checksum = sha256_bytes(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"))
        return {
            "schema_version": "1.0",
            "status": "available",
            "openapi_sha256": checksum,
            "manifest_sha256": manifest_sha256,
            "runtime_identity": expected_identity,
            "title": cast(dict[str, Any], payload.get("info", {})).get("title", ""),
            "version": cast(dict[str, Any], payload.get("info", {})).get("version", ""),
            "endpoint_inventory": inventory,
            "document": payload,
            "drift_detected": False,
        }

    def _fetch_object(
        self,
        *,
        base_url: str,
        owned_port: int,
        endpoint: str,
        label: str,
    ) -> dict[str, Any]:
        normalized = normalize_runtime_url(
            base_url=base_url,
            method="GET",
            endpoint=endpoint,
            owned_port=owned_port,
        )
        try:
            with urllib_request.urlopen(normalized.url, timeout=3.0) as response:
                if 300 <= response.status < 400:
                    raise RuntimeContractError("OpenAPI redirects are not allowed")
                data = response.read(MAX_RESPONSE_BYTES + 1)
        except (HTTPError, URLError, TimeoutError) as exc:
            raise RuntimeContractError(f"{label} retrieval failed: {exc}") from exc
        if len(data) > MAX_RESPONSE_BYTES:
            raise RuntimeContractError(f"{label} document exceeded response budget")
        try:
            payload = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeContractError(f"{label} response was not valid JSON") from exc
        if not isinstance(payload, dict):
            raise RuntimeContractError(f"{label} document must be an object")
        return payload
