from __future__ import annotations

from typing import Any

_EVIDENCE_PACKS: dict[str, list[dict[str, Any]]] = {}


def store_evidence_pack(case_id: str, observations: list[dict[str, Any]]) -> None:
    _EVIDENCE_PACKS[case_id] = observations


def list_evidence_packs() -> dict[str, list[dict[str, Any]]]:
    return dict(_EVIDENCE_PACKS)
