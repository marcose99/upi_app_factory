from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping

from .models import GovernanceError


_UNSUPPORTED = re.compile(
    r"\b(certif(?:ied|ication)|regulator[- ]approved|rbi[- ]approved|legally compliant|"
    r"regulatory approval|government[- ]approved)\b", re.IGNORECASE
)


@dataclass(frozen=True)
class RegulatoryMetadata:
    alignment: str
    readiness_evidence: tuple[str, ...]

    @classmethod
    def parse(cls, value: object) -> "RegulatoryMetadata":
        if not isinstance(value, Mapping) or set(value) != {"alignment", "readiness_evidence"}:
            raise GovernanceError("regulatory metadata has invalid fields")
        alignment = value["alignment"]
        evidence = value["readiness_evidence"]
        if not isinstance(alignment, str) or not alignment or len(alignment) > 512:
            raise GovernanceError("alignment must be a bounded string")
        if not isinstance(evidence, (list, tuple)) or len(evidence) > 64 or not all(
            isinstance(item, str) and item and len(item) <= 512 for item in evidence
        ):
            raise GovernanceError("readiness evidence must be bounded strings")
        combined = " ".join((alignment, *evidence))
        if _UNSUPPORTED.search(combined):
            raise GovernanceError("unsupported approval or certification claim")
        return cls(alignment, tuple(evidence))


def validate_regulatory_metadata(value: object) -> RegulatoryMetadata:
    return RegulatoryMetadata.parse(value)
