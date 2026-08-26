"""Fact-derived generated-application maintenance and evolution contracts."""

from .lifecycle import (
    ChangeKind,
    ChangeRecord,
    ChangeType,
    MaintenanceLedger,
    MaintenanceModelError,
    RepairLocus,
)

__all__ = [
    "ChangeKind", "ChangeRecord", "ChangeType", "MaintenanceLedger",
    "MaintenanceModelError", "RepairLocus",
]
