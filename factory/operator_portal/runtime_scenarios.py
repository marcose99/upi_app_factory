from __future__ import annotations

from dataclasses import dataclass
import importlib
import json
import sys
import threading
import time
from typing import Any, Final, cast
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError

from factory.operator_portal.runtime_contracts import RuntimeContractError, sha256_bytes, utc_now
from factory.operator_portal.runtime_network_policy import (
    CONCURRENCY_LIMIT,
    MAX_PAYLOAD_BYTES,
    MAX_RESPONSE_BYTES,
    REQUEST_TIMEOUT_SECONDS,
    normalize_runtime_url,
    validate_redirect_location,
)
from factory.operator_portal.runtime_store import RuntimeStore, redact


@dataclass(frozen=True)
class RuntimeScenario:
    scenario_id: str
    category: str
    method: str
    endpoint: str
    payload: dict[str, Any] | None
    expected_status: int
    expected_json: dict[str, Any]


SCENARIO_CATALOG_VERSION: Final[str] = "1.0.0"


def scenario_catalog() -> dict[str, Any]:
    scenarios = [
        RuntimeScenario(
            "positive_create_dispute",
            "positive",
            "POST",
            "/disputes",
            _dispute_payload("PHASE50POSITIVE001", reason="Local mock-safe Phase 50 dispute."),
            201,
            {"certification_boundary": "certification_ready_not_certified"},
        ),
        RuntimeScenario(
            "negative_invalid_request",
            "negative",
            "POST",
            "/disputes",
            {"transaction_ref": "bad"},
            422,
            {"code": "RequestValidationError"},
        ),
        RuntimeScenario(
            "boundary_long_reason",
            "boundary",
            "POST",
            "/disputes",
            _dispute_payload("PHASE50BOUNDARY001", reason="Local boundary scenario with a detailed but synthetic reviewer narrative."),
            201,
            {"certification_boundary": "certification_ready_not_certified"},
        ),
        RuntimeScenario(
            "idempotency_replay",
            "idempotency",
            "POST",
            "/disputes",
            _dispute_payload("PHASE50REPLAY001", reason="Local replay scenario."),
            201,
            {"certification_boundary": "certification_ready_not_certified", "replay_status": 201},
        ),
        RuntimeScenario(
            "resilience_missing_dispute",
            "resilience",
            "GET",
            "/disputes/DSP_MISSING",
            None,
            404,
            {"code": "HTTPException"},
        ),
        RuntimeScenario(
            "security_strict_extra_rejection",
            "security",
            "POST",
            "/disputes",
            {
                **_dispute_payload("PHASE50SECURITY001", reason="Strict input boundary scenario."),
                "unexpected_secret": "synthetic-only",
            },
            422,
            {"code": "RequestValidationError"},
        ),
        RuntimeScenario("timeout_budget_health", "timeout", "GET", "/health", None, 200, {"status": "ok"}),
        RuntimeScenario("readiness_contract", "positive", "GET", "/ready", None, 200, {"dependencies.sqlite.real_payment_calls_allowed": False}),
    ]
    return {
        "schema_version": "1.0",
        "version": SCENARIO_CATALOG_VERSION,
        "categories": sorted({scenario.category for scenario in scenarios}),
        "scenarios": [
            {
                "id": scenario.scenario_id,
                "category": scenario.category,
                "method": scenario.method,
                "endpoint": scenario.endpoint,
                "payload": scenario.payload,
                "expected": {
                    "status": scenario.expected_status,
                    "json": scenario.expected_json,
                },
            }
            for scenario in scenarios
        ],
    }


class ScenarioRunner:
    def __init__(self, *, store: RuntimeStore) -> None:
        self.store = store
        self._semaphore = threading.BoundedSemaphore(CONCURRENCY_LIMIT)

    def run_all(self, *, run_id: str, base_url: str, owned_port: int) -> dict[str, Any]:
        results = [self.run_one(run_id=run_id, base_url=base_url, owned_port=owned_port, scenario=item) for item in scenario_catalog()["scenarios"]]
        passed = all(result["passed"] for result in results)
        payload = {
            "schema_version": "1.0",
            "run_id": run_id,
            "catalog_version": SCENARIO_CATALOG_VERSION,
            "started_at_utc": results[0]["started_at_utc"] if results else utc_now(),
            "completed_at_utc": utc_now(),
            "passed": passed,
            "decision": "GO" if passed else "NO_GO",
            "results": results,
        }
        self.store.atomic_write_json(self.store.scenario_path(run_id), payload)
        self.store.append_event(run_id, "runtime_scenarios_completed", {"passed": passed, "result_count": len(results)})
        return payload

    def run_one(self, *, run_id: str, base_url: str, owned_port: int, scenario: dict[str, Any]) -> dict[str, Any]:
        if not self._semaphore.acquire(blocking=False):
            raise RuntimeContractError("scenario concurrency budget exceeded")
        started = time.monotonic()
        started_at = utc_now()
        try:
            scenario_id = str(scenario["id"])
            method = str(scenario["method"])
            endpoint = str(scenario["endpoint"])
            expected = cast(dict[str, Any], scenario["expected"])
            payload = cast(dict[str, Any] | None, scenario.get("payload"))
            response = self._request(base_url=base_url, owned_port=owned_port, method=method, endpoint=endpoint, payload=payload)
            replay_response: dict[str, Any] | None = None
            expected_json = cast(dict[str, Any], expected.get("json", {}))
            if "replay_status" in expected_json:
                replay_response = self._request(base_url=base_url, owned_port=owned_port, method=method, endpoint=endpoint, payload=payload)
            assertions = self._assertions(response=response, expected_status=int(expected["status"]), expected_json=expected_json, replay_response=replay_response)
            passed = all(item["passed"] for item in assertions)
            material = {
                "scenario_id": scenario_id,
                "request": {"method": method, "endpoint": endpoint, "payload": redact(payload or {})},
                "response": redact(response),
                "assertions": assertions,
            }
            result = {
                "scenario_id": scenario_id,
                "category": scenario["category"],
                "started_at_utc": started_at,
                "duration_ms": int((time.monotonic() - started) * 1000),
                "passed": passed,
                "request_sha256": sha256_bytes(json.dumps(material["request"], sort_keys=True).encode("utf-8")),
                "response_sha256": sha256_bytes(json.dumps(material["response"], sort_keys=True).encode("utf-8")),
                "result_sha256": sha256_bytes(json.dumps(material, sort_keys=True).encode("utf-8")),
                "assertions": assertions,
            }
            self.store.append_event(run_id, "runtime_scenario_executed", result)
            return result
        finally:
            self._semaphore.release()

    def _request(self, *, base_url: str, owned_port: int, method: str, endpoint: str, payload: dict[str, Any] | None) -> dict[str, Any]:
        normalized = normalize_runtime_url(base_url=base_url, method=method, endpoint=endpoint, owned_port=owned_port)
        body = None
        headers = {"Accept": "application/json"}
        if endpoint.startswith("/disputes"):
            headers["Authorization"] = f"Bearer {self._local_runtime_token()}"
            headers["Idempotency-Key"] = _idempotency_key(payload)
        if payload is not None:
            body = json.dumps(payload, sort_keys=True).encode("utf-8")
            if len(body) > MAX_PAYLOAD_BYTES:
                raise RuntimeContractError("scenario payload exceeded request budget")
            headers["Content-Type"] = "application/json"
        req = urllib_request.Request(normalized.url, data=body, headers=headers, method=normalized.method)
        opener = urllib_request.build_opener(NoRedirectHandler)
        try:
            with opener.open(req, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                if 300 <= response.status < 400:
                    validate_redirect_location(base_url=base_url, location=response.headers.get("Location", ""), owned_port=owned_port)
                    raise RuntimeContractError("redirects are blocked for scenario execution")
                data = response.read(MAX_RESPONSE_BYTES + 1)
                status = response.status
        except HTTPError as exc:
            data = exc.read(MAX_RESPONSE_BYTES + 1)
            status = exc.code
        except (URLError, TimeoutError) as exc:
            raise RuntimeContractError(f"scenario request failed: {exc}") from exc
        if len(data) > MAX_RESPONSE_BYTES:
            raise RuntimeContractError("scenario response exceeded response budget")
        try:
            json_payload: Any = json.loads(data.decode("utf-8"))
        except json.JSONDecodeError:
            json_payload = {"raw": data.decode("utf-8", errors="replace")}
        return {"status": status, "json": json_payload}

    def _local_runtime_token(self) -> str:
        generated_parent = (
            self.store.project_root
            / "workspace/factory_generated/upi_dispute_resolution"
        )
        generated_parent_text = generated_parent.as_posix()
        if generated_parent_text not in sys.path:
            sys.path.insert(0, generated_parent_text)
        try:
            identity = importlib.import_module(
                "generated_application.app.security.identity"
            )
            token = identity.issue_local_test_token(
                subject="phase50-scenario-runner",
                scopes=("dispute:create", "dispute:read", "dispute:read:any"),
                roles=(),
            )
        except (AttributeError, ImportError) as exc:
            raise RuntimeContractError("local generated identity helper unavailable") from exc
        return str(token)

    def _assertions(self, *, response: dict[str, Any], expected_status: int, expected_json: dict[str, Any], replay_response: dict[str, Any] | None) -> list[dict[str, Any]]:
        assertions = [{"name": "status", "passed": response["status"] == expected_status, "expected": expected_status, "actual": response["status"]}]
        for dotted, expected_value in expected_json.items():
            if dotted == "replay_status":
                actual = replay_response["status"] if replay_response else None
            else:
                actual = _select(response["json"], dotted)
            assertions.append({"name": dotted, "passed": actual == expected_value, "expected": expected_value, "actual": actual})
        return assertions


class NoRedirectHandler(urllib_request.HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> None:
        return None


def _select(payload: Any, dotted: str) -> Any:
    current = payload
    for part in dotted.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _idempotency_key(payload: dict[str, Any] | None) -> str:
    if isinstance(payload, dict):
        transaction_ref = str(payload.get("transaction_ref", "")).strip()
        if transaction_ref:
            return f"phase50-{transaction_ref.lower()}"
    return "phase50-read-only"


def _dispute_payload(transaction_ref: str, *, reason: str) -> dict[str, Any]:
    return {
        "transaction_ref": transaction_ref,
        "customer_upi": "phase50@upi",
        "reason": reason,
    }
