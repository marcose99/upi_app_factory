from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, TypeVar


T = TypeVar("T")


class AdapterTimeoutError(RuntimeError):
    pass


class AdapterCircuitOpenError(RuntimeError):
    pass


class AdapterBackpressureError(RuntimeError):
    pass


class AdapterPayloadTooLargeError(RuntimeError):
    pass


class AdapterRateLimitError(RuntimeError):
    pass


@dataclass(frozen=True)
class AdapterResilienceContract:
    adapter_name: str
    timeout_ms: int = 250
    retry_budget: int = 1
    jitter_ms: int = 25
    circuit_breaker_failure_threshold: int = 3
    circuit_breaker_reset_ms: int = 30_000
    rate_limit_per_minute: int = 60
    max_payload_bytes: int = 16_384
    degraded_mode: str = "return_local_manual_review_decision"
    live_provider_calls_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "adapter_name": self.adapter_name,
            "timeout_ms": self.timeout_ms,
            "retry_budget": self.retry_budget,
            "jitter_ms": self.jitter_ms,
            "circuit_breaker_failure_threshold": self.circuit_breaker_failure_threshold,
            "circuit_breaker_reset_ms": self.circuit_breaker_reset_ms,
            "rate_limit_per_minute": self.rate_limit_per_minute,
            "max_payload_bytes": self.max_payload_bytes,
            "degraded_mode": self.degraded_mode,
            "live_provider_calls_allowed": self.live_provider_calls_allowed,
        }


MOCK_ADAPTER_CONTRACTS = (
    AdapterResilienceContract(adapter_name="mock_upi_switch"),
    AdapterResilienceContract(adapter_name="mock_core_banking"),
    AdapterResilienceContract(adapter_name="mock_customer_notification"),
    AdapterResilienceContract(adapter_name="mock_dispute_evidence_store"),
)


class DeterministicResilientAdapter:
    def __init__(
        self,
        contract: AdapterResilienceContract,
        *,
        clock_ms: Callable[[], int],
        in_flight: int = 0,
        max_in_flight: int = 4,
    ) -> None:
        self.contract = contract
        self.clock_ms = clock_ms
        self.in_flight = in_flight
        self.max_in_flight = max_in_flight
        self.consecutive_failures = 0
        self.circuit_opened_at_ms: int | None = None
        self.call_timestamps_ms: list[int] = []

    def call(
        self,
        operation: Callable[[], T],
        *,
        payload: bytes | bytearray | str | dict[str, Any] | list[Any] | None = None,
    ) -> T | dict[str, object]:
        self._guard_payload(payload)
        self._guard_backpressure()
        self._guard_rate_limit()
        self._guard_circuit()
        attempts = self.contract.retry_budget + 1
        last_error: Exception | None = None
        for _ in range(attempts):
            started = self.clock_ms()
            self.in_flight += 1
            try:
                result = operation()
                elapsed = self.clock_ms() - started
                if elapsed > self.contract.timeout_ms:
                    raise AdapterTimeoutError("adapter timeout budget exceeded")
                self.consecutive_failures = 0
                self.circuit_opened_at_ms = None
                return result
            except Exception as exc:
                last_error = exc
                self.consecutive_failures += 1
                if self.consecutive_failures >= self.contract.circuit_breaker_failure_threshold:
                    self.circuit_opened_at_ms = self.clock_ms()
                    return self.degraded_response(str(exc))
            finally:
                self.in_flight -= 1
        assert last_error is not None
        return self.degraded_response(str(last_error))

    def degraded_response(self, reason: str) -> dict[str, object]:
        return {
            "adapter_name": self.contract.adapter_name,
            "mode": self.contract.degraded_mode,
            "reason": reason,
            "live_provider_calls_allowed": False,
        }

    def _guard_backpressure(self) -> None:
        if self.in_flight >= self.max_in_flight:
            raise AdapterBackpressureError("adapter backpressure budget exceeded")

    def _guard_payload(self, payload: bytes | bytearray | str | dict[str, Any] | list[Any] | None) -> None:
        if payload is None:
            return
        if isinstance(payload, (bytes, bytearray)):
            size = len(payload)
        elif isinstance(payload, str):
            size = len(payload.encode("utf-8"))
        else:
            rendered = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            size = len(rendered.encode("utf-8"))
        if size > self.contract.max_payload_bytes:
            raise AdapterPayloadTooLargeError("adapter payload byte budget exceeded")

    def _guard_rate_limit(self) -> None:
        now = self.clock_ms()
        window_start = now - 60_000
        self.call_timestamps_ms = [
            timestamp for timestamp in self.call_timestamps_ms if timestamp > window_start
        ]
        if len(self.call_timestamps_ms) >= self.contract.rate_limit_per_minute:
            raise AdapterRateLimitError("adapter deterministic rate budget exceeded")
        self.call_timestamps_ms.append(now)

    def _guard_circuit(self) -> None:
        if self.circuit_opened_at_ms is None:
            return
        elapsed = self.clock_ms() - self.circuit_opened_at_ms
        if elapsed < self.contract.circuit_breaker_reset_ms:
            raise AdapterCircuitOpenError("adapter circuit is open")
        self.circuit_opened_at_ms = None
        self.consecutive_failures = 0
