from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class ExistingSystemAdapter(Protocol):
    name: str

    def available(self) -> bool: ...

    def contract(self) -> dict[str, str]: ...


@dataclass(frozen=True)
class LifecycleOrchestratorAdapter:
    name: str = "tools.lifecycle_orchestrator"

    def available(self) -> bool:
        return importlib.util.find_spec("tools.lifecycle_orchestrator") is not None

    def contract(self) -> dict[str, str]:
        return {
            "adapter": self.name,
            "entrypoint": "bin/upi-app-factory-lifecycle",
            "mode": "delegating import/command contract; implementation is not copied",
        }


@dataclass(frozen=True)
class AutonomousSupervisorAdapter:
    name: str = "tools.autonomous_supervisor"

    def available(self) -> bool:
        return importlib.util.find_spec("tools.autonomous_supervisor") is not None

    def contract(self) -> dict[str, str]:
        return {
            "adapter": self.name,
            "entrypoint": "tools.autonomous_supervisor.engine.AutonomousCampaignSupervisor",
            "mode": (
                "contract reference for future coordination; "
                "historical closures are attested only"
            ),
        }


def closure_attestation(phase_id: str, evidence_path: Path) -> dict[str, str]:
    return {
        "phase_id": phase_id,
        "evidence_path": str(evidence_path),
        "regeneration": "forbidden during later campaign execution",
    }
