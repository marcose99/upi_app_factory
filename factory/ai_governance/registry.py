from __future__ import annotations

from dataclasses import dataclass

from .models import GovernanceError


@dataclass(frozen=True)
class AISystem:
    system_id: str
    version: str
    enabled: bool = True

    def __post_init__(self) -> None:
        if not self.system_id or not self.version:
            raise GovernanceError("AI systems require explicit identity and version")


class AISystemRegistry:
    def __init__(self) -> None:
        self._systems: dict[tuple[str, str], AISystem] = {}

    def register(self, system: AISystem) -> None:
        key = (system.system_id, system.version)
        if key in self._systems:
            raise GovernanceError("duplicate AI system identity and version")
        self._systems[key] = system

    def require(self, system_id: str, version: str) -> AISystem:
        if not system_id or not version:
            raise GovernanceError("unversioned AI system")
        try:
            system = self._systems[(system_id, version)]
        except KeyError as exc:
            raise GovernanceError("unknown AI system") from exc
        if not system.enabled:
            raise GovernanceError("AI system is disabled")
        return system

    resolve = require
