from __future__ import annotations

from statistics import median
from typing import Any


def pass_rate(values: list[bool]) -> float:
    return sum(1 for value in values if value) / len(values) if values else 0.0


def percentile(values: list[float], percentile_value: float) -> float | str:
    if not values:
        return "NOT_RUN"
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = round((len(ordered) - 1) * percentile_value)
    return ordered[rank]


def latency_summary(values: list[float]) -> dict[str, float | str]:
    return {"p50_ms": median(values) if values else "NOT_RUN", "p95_ms": percentile(values, 0.95)}


def retrieval_metrics(results: list[dict[str, Any]], *, top_k: int) -> dict[str, float]:
    hit_count = 0
    reciprocal_total = 0.0
    rejected = 0
    for result in results:
        expected = set(result["expected_source_ids"])
        retrieved = list(result["retrieved_source_ids"])[:top_k]
        if expected.intersection(retrieved):
            hit_count += 1
        reciprocal_total += next((1.0 / (idx + 1) for idx, source_id in enumerate(retrieved) if source_id in expected), 0.0)
        if not set(result.get("irrelevant_source_ids", [])).intersection(retrieved):
            rejected += 1
    total = len(results) or 1
    return {"hit_at_k": hit_count / total, "mrr": reciprocal_total / total, "irrelevant_rejection_rate": rejected / total}
