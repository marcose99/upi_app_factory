from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GetDisputeQuery:
    dispute_id: str
    correlation_id: str
