from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Protocol

from .contracts import AgentRuntimeState, RuntimeMode
from .ledger import JsonlLedger
from .orchestrator import GovernedAgentRuntime


class AdapterName(str, Enum):
    LOCAL_DETERMINISTIC = "local_deterministic"
    LANGGRAPH = "langgraph"
    OPENAI_AGENTS = "openai_agents"


class AdapterStatus(str, Enum):
    AVAILABLE = "available"
    NOT_INSTALLED = "not_installed"
    CONFIG_MISSING = "config_missing"
    BLOCKED_BY_POLICY = "blocked_by_policy"
    EXECUTED = "executed"


@dataclass(frozen=True)
class AdapterCapability:
    adapter_name: AdapterName
    status: AdapterStatus
    reason: str
    requires_network: bool
    requires_secret: bool
    requires_human_approval: bool


@dataclass
class AdapterExecutionResult:
    adapter_name: AdapterName
    status: AdapterStatus
    message: str
    runtime_state: dict[str, object] | None = None
    metrics: dict[str, int | str | float] = field(default_factory=dict)


class AgentExecutionAdapter(Protocol):
    adapter_name: AdapterName

    def execute(self) -> AdapterExecutionResult:
        ...


class LocalDeterministicAdapter:
    adapter_name = AdapterName.LOCAL_DETERMINISTIC

    def __init__(self, *, app_id: str, run_id: str, workspace_root: Path) -> None:
        self.runtime = GovernedAgentRuntime(
            app_id=app_id,
            run_id=run_id,
            workspace_root=workspace_root,
            runtime_mode=RuntimeMode.LOCAL_DETERMINISTIC,
        )

    def execute(self) -> AdapterExecutionResult:
        state: AgentRuntimeState = self.runtime.run_dry_run()
        return AdapterExecutionResult(
            adapter_name=self.adapter_name,
            status=AdapterStatus.EXECUTED,
            message="Executed local deterministic governed agent adapter.",
            runtime_state=state.to_jsonable(),
            metrics={
                "completed_agents": len(state.completed_agents),
                "runtime_mode": state.runtime_mode.value,
            },
        )


class AdapterCapabilityDetector:
    def detect(self) -> list[AdapterCapability]:
        return [
            AdapterCapability(
                adapter_name=AdapterName.LOCAL_DETERMINISTIC,
                status=AdapterStatus.AVAILABLE,
                reason="Built into this factory and does not need network access.",
                requires_network=False,
                requires_secret=False,
                requires_human_approval=False,
            ),
            self._detect_langgraph(),
            self._detect_openai_agents(),
        ]

    def _detect_langgraph(self) -> AdapterCapability:
        if importlib.util.find_spec("langgraph") is None:
            return AdapterCapability(
                adapter_name=AdapterName.LANGGRAPH,
                status=AdapterStatus.NOT_INSTALLED,
                reason="langgraph package is not installed in the active environment.",
                requires_network=False,
                requires_secret=False,
                requires_human_approval=True,
            )
        return AdapterCapability(
            adapter_name=AdapterName.LANGGRAPH,
            status=AdapterStatus.AVAILABLE,
            reason="langgraph package is importable; execution adapter remains policy-gated.",
            requires_network=False,
            requires_secret=False,
            requires_human_approval=True,
        )

    def _detect_openai_agents(self) -> AdapterCapability:
        openai_importable = importlib.util.find_spec("openai") is not None
        has_api_key = bool(os.environ.get("OPENAI_API_KEY"))
        if not openai_importable:
            return AdapterCapability(
                adapter_name=AdapterName.OPENAI_AGENTS,
                status=AdapterStatus.NOT_INSTALLED,
                reason="openai package is not installed in the active environment.",
                requires_network=True,
                requires_secret=True,
                requires_human_approval=True,
            )
        if not has_api_key:
            return AdapterCapability(
                adapter_name=AdapterName.OPENAI_AGENTS,
                status=AdapterStatus.CONFIG_MISSING,
                reason="openai package is importable but OPENAI_API_KEY is not configured.",
                requires_network=True,
                requires_secret=True,
                requires_human_approval=True,
            )
        return AdapterCapability(
            adapter_name=AdapterName.OPENAI_AGENTS,
            status=AdapterStatus.BLOCKED_BY_POLICY,
            reason=(
                "OpenAI-backed execution has credentials available but remains blocked "
                "until explicit human approval and cost/telemetry controls are enabled."
            ),
            requires_network=True,
            requires_secret=True,
            requires_human_approval=True,
        )


class GovernedAdapterExecutor:
    def __init__(self, *, app_id: str, run_id: str, workspace_root: Path) -> None:
        self.app_id = app_id
        self.run_id = run_id
        self.workspace_root = workspace_root
        self.ledger_root = workspace_root / "generation_runs" / run_id / "agent_runtime_ledgers"
        self.adapter_ledger = JsonlLedger(self.ledger_root / "adapter_execution_ledger.jsonl")
        self.capability_ledger = JsonlLedger(self.ledger_root / "adapter_capability_ledger.jsonl")

    def capability_report(self) -> list[AdapterCapability]:
        capabilities = AdapterCapabilityDetector().detect()
        for capability in capabilities:
            self.capability_ledger.append(
                "adapter_capability_detected",
                {
                    "adapter_name": capability.adapter_name.value,
                    "status": capability.status.value,
                    "reason": capability.reason,
                    "requires_network": capability.requires_network,
                    "requires_secret": capability.requires_secret,
                    "requires_human_approval": capability.requires_human_approval,
                },
            )
        return capabilities

    def execute_default_governed_adapter(self) -> AdapterExecutionResult:
        result = LocalDeterministicAdapter(
            app_id=self.app_id,
            run_id=self.run_id,
            workspace_root=self.workspace_root,
        ).execute()
        self.adapter_ledger.append(
            "adapter_execution_completed",
            {
                "adapter_name": result.adapter_name.value,
                "status": result.status.value,
                "message": result.message,
                "metrics": result.metrics,
            },
        )
        return result
