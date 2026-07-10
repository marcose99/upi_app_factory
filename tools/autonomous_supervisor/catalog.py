from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


class CatalogError(RuntimeError):
    """Raised when autonomous repair configuration is invalid."""


def load_json_object(path: Path, label: str) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise CatalogError(f"{label} must be a JSON object")
    return value


@dataclass(frozen=True)
class RepairRule:
    repair_id: str
    automatic: bool
    eligible_gates: tuple[str, ...]
    max_attempts: int
    candidate_scope_required: bool
    safe_fix_only: bool
    risk: str

    @classmethod
    def from_object(cls, value: dict[str, Any]) -> "RepairRule":
        repair_id = value.get("repair_id")
        gates = value.get("eligible_gates")
        if not isinstance(repair_id, str) or not repair_id:
            raise CatalogError("repair_id must be a non-empty string")
        if not isinstance(gates, list) or not all(
            isinstance(item, str) and item for item in gates
        ):
            raise CatalogError(
                f"eligible_gates is invalid for {repair_id}"
            )
        max_attempts = value.get("max_attempts", 1)
        if not isinstance(max_attempts, int) or max_attempts < 1:
            raise CatalogError(
                f"max_attempts is invalid for {repair_id}"
            )
        return cls(
            repair_id=repair_id,
            automatic=bool(value.get("automatic", False)),
            eligible_gates=tuple(gates),
            max_attempts=max_attempts,
            candidate_scope_required=bool(
                value.get("candidate_scope_required", True)
            ),
            safe_fix_only=bool(value.get("safe_fix_only", True)),
            risk=str(value.get("risk", "UNKNOWN")),
        )


class RepairCatalog:
    def __init__(self, rules: tuple[RepairRule, ...]) -> None:
        self.rules = rules

    @classmethod
    def load(cls, path: Path) -> "RepairCatalog":
        root = load_json_object(path, "Repair catalog")
        raw_rules = root.get("repairs")
        if not isinstance(raw_rules, list):
            raise CatalogError("repairs must be a list")
        rules = tuple(
            RepairRule.from_object(item)
            for item in raw_rules
            if isinstance(item, dict)
        )
        if len(rules) != len(raw_rules):
            raise CatalogError("Every repair entry must be an object")
        return cls(rules)

    def automatic_rule_for_gate(
        self,
        gate: str,
    ) -> RepairRule | None:
        for rule in self.rules:
            if rule.automatic and gate in rule.eligible_gates:
                return rule
        return None
