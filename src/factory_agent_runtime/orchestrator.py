from __future__ import annotations

from pathlib import Path

from .contracts import AgentDefinition, AgentRuntimeState, AgentStepResult, RuntimeMode
from .ledger import JsonlLedger
from .registry import default_agent_registry, default_tool_registry


class GovernedAgentRuntime:
    def __init__(
        self,
        *,
        app_id: str,
        run_id: str,
        workspace_root: Path,
        runtime_mode: RuntimeMode = RuntimeMode.DRY_RUN,
    ) -> None:
        self.app_id = app_id
        self.run_id = run_id
        self.workspace_root = workspace_root
        self.runtime_mode = runtime_mode
        self.agent_registry = default_agent_registry()
        self.tool_registry = default_tool_registry()
        self.ledger_root = workspace_root / "generation_runs" / run_id / "agent_runtime_ledgers"
        self.handoff_ledger = JsonlLedger(self.ledger_root / "handoff_ledger.jsonl")
        self.tool_ledger = JsonlLedger(self.ledger_root / "tool_execution_ledger.jsonl")
        self.runtime_ledger = JsonlLedger(self.ledger_root / "runtime_event_ledger.jsonl")

    def run_dry_run(self) -> AgentRuntimeState:
        state = AgentRuntimeState(
            run_id=self.run_id,
            app_id=self.app_id,
            runtime_mode=self.runtime_mode,
            metrics={
                "agents_registered": len(self.agent_registry),
                "tools_registered": len(self.tool_registry),
                "agent_steps_completed": 0,
            },
        )
        self.runtime_ledger.append("runtime_started", state.to_jsonable())

        previous_agent: str | None = None
        for agent in self.agent_registry:
            result = self._execute_agent_dry_run(agent)
            state.current_agent = agent.name
            state.completed_agents.append(agent.name)
            state.metrics["agent_steps_completed"] = len(state.completed_agents)
            self.runtime_ledger.append("agent_step_completed", result.__dict__)
            if previous_agent is not None:
                self.handoff_ledger.append(
                    "agent_handoff",
                    {
                        "from_agent": previous_agent,
                        "to_agent": agent.name,
                        "run_id": self.run_id,
                        "handoff_mode": "dry_run",
                    },
                )
            previous_agent = agent.name

        state.current_agent = None
        self.runtime_ledger.append("runtime_completed", state.to_jsonable())
        return state

    def _execute_agent_dry_run(self, agent: AgentDefinition) -> AgentStepResult:
        for tool_name in agent.allowed_tools:
            self.tool_ledger.append(
                "tool_authorized_for_agent",
                {
                    "agent_name": agent.name,
                    "tool_name": tool_name,
                    "mode": self.runtime_mode.value,
                },
            )
        return AgentStepResult(
            agent_name=agent.name,
            status="dry_run_complete",
            message=f"{agent.name} registered and executed in dry-run mode.",
            artifacts=list(agent.output_artifacts),
            metrics={"allowed_tool_count": len(agent.allowed_tools)},
        )
