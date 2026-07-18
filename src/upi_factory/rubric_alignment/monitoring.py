from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from upi_factory.rubric_alignment.metrics import latency_summary
from upi_factory.rubric_alignment.utils import redact


@dataclass
class Monitor:
    trace_id: str
    timings_ms: dict[str, float] = field(default_factory=dict)
    counts: Counter[str] = field(default_factory=Counter)
    logs: list[dict[str, object]] = field(default_factory=list)

    def time_stage(self, stage: str) -> "_Timer":
        return _Timer(self, stage)

    def count(self, name: str, amount: int = 1) -> None:
        self.counts[name] += amount

    def log(self, event: str, payload: Any) -> None:
        self.logs.append({"trace_id": self.trace_id, "event": event, "payload": redact(str(payload))})

    def summary(self, latencies: list[float]) -> dict[str, object]:
        return {
            "trace_id": self.trace_id,
            "stage_timings_ms": self.timings_ms,
            "counts": dict(self.counts),
            "latency": latency_summary(latencies),
            "redacted_logs": self.logs,
        }


class _Timer:
    def __init__(self, monitor: Monitor, stage: str) -> None:
        self.monitor = monitor
        self.stage = stage
        self.started = 0.0

    def __enter__(self) -> None:
        self.started = time.perf_counter()

    def __exit__(self, *_: object) -> None:
        self.monitor.timings_ms[self.stage] = (time.perf_counter() - self.started) * 1000
