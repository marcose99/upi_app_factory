"""Governed deterministic role-agent simulation package."""

from factory.agents.contracts import AGENT_SEQUENCE, AgentOutput
from factory.agents.role_runner import run_multi_agent_simulation

__all__ = ["AGENT_SEQUENCE", "AgentOutput", "run_multi_agent_simulation"]
