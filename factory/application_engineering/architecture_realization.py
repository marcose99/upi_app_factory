"""Architecture realization contract loading and adapter lookup."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from factory.architecture_decisioning.canonical import canonical_sha256
from factory.architecture_decisioning.models import ArchitectureDecisionError, ArchitectureHumanGate

from .architecture_adapters import ArchitectureAdapter


def load_architecture_realization_contract(path: Path) -> dict[str, Any]:
    try:
        contract = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ArchitectureDecisionError("cannot load architecture realization contract") from exc
    if not isinstance(contract, dict):
        raise ArchitectureDecisionError("architecture realization contract must be an object")
    supplied = contract.get("contract_digest")
    body = {key: value for key, value in contract.items() if key != "contract_digest"}
    expected = canonical_sha256(body)
    if supplied is not None and supplied != expected:
        raise ArchitectureDecisionError("architecture realization contract digest is invalid")
    contract["contract_digest"] = expected
    return contract


def get_architecture_adapter(pattern_id: str, contract: Mapping[str, Any]) -> ArchitectureAdapter:
    for row in contract.get("patterns", []):
        if isinstance(row, Mapping) and row.get("pattern_id") == pattern_id:
            if row.get("execution_state") != "EXECUTABLE":
                raise ArchitectureDecisionError("architecture pattern is not executable")
            return ArchitectureAdapter(pattern_id, str(row.get("adapter_id")))
    unsupported = contract.get("unsupported_patterns", {})
    disposition = unsupported.get(pattern_id) if isinstance(unsupported, Mapping) else None
    if disposition == "HUMAN_GATE":
        raise ArchitectureHumanGate("architecture pattern requires human enablement")
    raise ArchitectureDecisionError("architecture pattern has no supported realization adapter")
