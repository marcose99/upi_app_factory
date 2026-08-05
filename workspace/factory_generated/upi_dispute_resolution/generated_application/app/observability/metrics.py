from __future__ import annotations

from dataclasses import dataclass, field
import math
import time


ALLOWED_HTTP_METHODS = {"GET", "POST"}
ALLOWED_ROUTES = {
    "/startup",
    "/live",
    "/ready",
    "/drain",
    "/health",
    "/metrics",
    "/runtime/diagnostics",
    "/disputes",
    "/v1/disputes",
}
ALLOWED_OUTCOMES = {"success", "error", "draining"}
LATENCY_BUCKETS_SECONDS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5)


def _bounded(value: str, allowed: set[str], fallback: str) -> str:
    return value if value in allowed else fallback


def route_label(path: str) -> str:
    if path.startswith("/disputes"):
        return "/disputes"
    if path.startswith("/v1/disputes"):
        return "/v1/disputes"
    return _bounded(path, ALLOWED_ROUTES, "other")


@dataclass
class Histogram:
    buckets: tuple[float, ...]
    counts: dict[float, int] = field(default_factory=dict)
    count: int = 0
    total: float = 0.0

    def observe(self, value: float) -> None:
        self.count += 1
        self.total += value
        for bucket in self.buckets:
            if value <= bucket:
                self.counts[bucket] = self.counts.get(bucket, 0) + 1


class Metrics:
    def __init__(self) -> None:
        self.counters: dict[str, int] = {}
        self.http_request_counts: dict[tuple[str, str, str], int] = {}
        self.http_latency = Histogram(LATENCY_BUCKETS_SECONDS)
        self.business_events: dict[tuple[str, str], int] = {}

    def increment(self, name: str, value: int = 1) -> None:
        self.counters[name] = self.counters.get(name, 0) + value

    def record_http(
        self,
        *,
        method: str,
        route: str,
        outcome: str,
        duration_seconds: float,
    ) -> None:
        labels = (
            _bounded(method.upper(), ALLOWED_HTTP_METHODS, "OTHER"),
            route_label(route),
            _bounded(outcome, ALLOWED_OUTCOMES, "error"),
        )
        self.http_request_counts[labels] = (
            self.http_request_counts.get(labels, 0) + 1
        )
        self.http_latency.observe(max(duration_seconds, 0.0))

    def record_business_event(self, *, event_type: str, outcome: str) -> None:
        labels = (
            event_type[:80],
            _bounded(outcome, ALLOWED_OUTCOMES, "error"),
        )
        self.business_events[labels] = self.business_events.get(labels, 0) + 1

    def snapshot(self) -> dict[str, object]:
        return {
            "counters": dict(self.counters),
            "http_requests": {
                "|".join(labels): value
                for labels, value in sorted(self.http_request_counts.items())
            },
            "http_request_duration_seconds": {
                "count": self.http_latency.count,
                "sum": round(self.http_latency.total, 9),
                "buckets": {
                    str(bucket): self.http_latency.counts.get(bucket, 0)
                    for bucket in self.http_latency.buckets
                },
            },
            "business_events": {
                "|".join(labels): value
                for labels, value in sorted(self.business_events.items())
            },
        }

    def openmetrics(self) -> str:
        lines = [
            "# HELP upi_app_factory_http_requests_total HTTP requests processed locally.",
            "# TYPE upi_app_factory_http_requests_total counter",
        ]
        for (method, route, outcome), value in sorted(self.http_request_counts.items()):
            lines.append(
                "upi_app_factory_http_requests_total"
                f'{{method="{method}",route="{route}",outcome="{outcome}"}} {value}'
            )

        lines.extend(
            [
                "# HELP upi_app_factory_http_request_duration_seconds "
                "HTTP request duration in seconds.",
                "# TYPE upi_app_factory_http_request_duration_seconds histogram",
            ]
        )
        for bucket in self.http_latency.buckets:
            count = self.http_latency.counts.get(bucket, 0)
            lines.append(
                "upi_app_factory_http_request_duration_seconds_bucket"
                f'{{le="{bucket:g}"}} {count}'
            )
        lines.append(
            "upi_app_factory_http_request_duration_seconds_bucket"
            f'{{le="+Inf"}} {self.http_latency.count}'
        )
        lines.append(
            "upi_app_factory_http_request_duration_seconds_sum "
            f"{self.http_latency.total:.9f}"
        )
        lines.append(
            "upi_app_factory_http_request_duration_seconds_count "
            f"{self.http_latency.count}"
        )

        lines.extend(
            [
                "# HELP upi_app_factory_business_events_total "
                "Bounded local business events.",
                "# TYPE upi_app_factory_business_events_total counter",
            ]
        )
        for (event_type, outcome), value in sorted(self.business_events.items()):
            lines.append(
                "upi_app_factory_business_events_total"
                f'{{event_type="{event_type}",outcome="{outcome}"}} {value}'
            )
        lines.append("# EOF")
        return "\n".join(lines) + "\n"


METRICS = Metrics()


class Timer:
    def __init__(self) -> None:
        self.started = time.perf_counter()

    def elapsed_seconds(self) -> float:
        return time.perf_counter() - self.started


def percentile(values: list[float], percentile_value: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = math.ceil((percentile_value / 100.0) * len(ordered)) - 1
    return ordered[max(0, min(rank, len(ordered) - 1))]
