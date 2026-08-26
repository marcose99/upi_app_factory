"""Fail-closed gate for claims projected from canonical facts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .facts import EvidenceGraph, FactModelError, FactStatus, _identifier


class FactualityError(FactModelError):
    """Raised when a claim lacks current, authoritative fact support."""


@dataclass(frozen=True)
class Claim:
    claim_id: str
    text: str
    fact_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        try:
            _identifier(self.claim_id, "claim_id")
        except FactModelError as exc:
            raise FactualityError(str(exc)) from exc
        if not isinstance(self.text, str) or not self.text.strip():
            raise FactualityError("claims require non-empty text")
        object.__setattr__(self, "fact_ids", tuple(self.fact_ids))
        if (
            not self.fact_ids
            or any(not isinstance(item, str) or not item.strip() for item in self.fact_ids)
            or len(self.fact_ids) != len(set(self.fact_ids))
        ):
            raise FactualityError("claims require unique supporting fact IDs")


def validate_factuality(
    claims: Iterable[Claim],
    graph: EvidenceGraph,
    current_sources: Mapping[str, tuple[str, str]],
) -> dict[str, Any]:
    """Validate every claim against current PROVEN facts or reject the projection."""
    claim_list = list(claims)
    if len({claim.claim_id for claim in claim_list}) != len(claim_list):
        raise FactualityError("claim IDs must be unique")
    node_ids = set(graph.node_ids())
    stale = set(graph.stale_nodes(current_sources))
    for claim in claim_list:
        missing = sorted(set(claim.fact_ids).difference(node_ids))
        if missing:
            raise FactualityError(
                f"claim {claim.claim_id} references unknown facts: {', '.join(missing)}"
            )
        unsupported = sorted(
            fact_id for fact_id in claim.fact_ids
            if graph.node(fact_id).status is not FactStatus.PROVEN or fact_id in stale
        )
        if unsupported:
            raise FactualityError(
                f"claim {claim.claim_id} lacks current PROVEN support: "
                f"{', '.join(unsupported)}"
            )
    return {
        "claim_count": len(claim_list),
        "gate": "DOCUMENT_AND_EVIDENCE_FACTUALITY_GATE",
        "status": "PROVEN",
        "validated_claim_ids": sorted(claim.claim_id for claim in claim_list),
    }
