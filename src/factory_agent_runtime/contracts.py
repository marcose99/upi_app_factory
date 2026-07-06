from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RuntimeMode(str, Enum):
    DRY_RUN = "dry_run"
    LOCAL_DETERMINISTIC = "local_deterministic"
    LANGGRAPH_PLANNED = "langgraph_planned"
    OPENAI_AGENTS_PLANNED = "openai_agents_planned"


@dataclass(frozen=True)
class AgentDefinition:
    name: str
    purpose: str
    allowed_tools: tuple[str, ...]
    output_artifacts: tuple[str, ...]
    requires_human_approval: bool = False


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    purpose: str
    destructive: bool
    requires_human_approval: bool
    allowed_paths: tuple[str, ...] = ()


@dataclass
class AgentStepResult:
    agent_name: str
    status: str
    message: str
    artifacts: list[str] = field(default_factory=list)
    metrics: dict[str, int | float | str] = field(default_factory=dict)


@dataclass
class AgentRuntimeState:
    run_id: str
    app_id: str
    runtime_mode: RuntimeMode
    current_agent: str | None = None
    completed_agents: list[str] = field(default_factory=list)
    blocked_reason: str | None = None
    metrics: dict[str, int | float | str] = field(default_factory=dict)

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "app_id": self.app_id,
            "runtime_mode": self.runtime_mode.value,
            "current_agent": self.current_agent,
            "completed_agents": list(self.completed_agents),
            "blocked_reason": self.blocked_reason,
            "metrics": dict(self.metrics),
        }
