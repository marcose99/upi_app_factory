from __future__ import annotations

from tools.governed_repairs.contracts import (
    GovernedRepair,
    RepairContext,
    RepairDecision,
)


class RepairRegistryError(RuntimeError):
    pass


class GovernedRepairRegistry:
    def __init__(self) -> None:
        self._repairs: dict[str, GovernedRepair] = {}

    def register(self, repair: GovernedRepair) -> None:
        if not repair.repair_id:
            raise RepairRegistryError("repair_id is required")
        if repair.repair_id in self._repairs:
            raise RepairRegistryError(f"Repair is already registered: {repair.repair_id}")
        self._repairs[repair.repair_id] = repair

    def get(self, repair_id: str) -> GovernedRepair:
        try:
            return self._repairs[repair_id]
        except KeyError as exc:
            raise RepairRegistryError(f"Unknown governed repair: {repair_id}") from exc

    def assess(self, repair_id: str, context: RepairContext) -> RepairDecision:
        return self.get(repair_id).assess(context)

    def ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._repairs))
