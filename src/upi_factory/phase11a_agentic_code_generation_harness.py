"""Compatibility import for Phase 11A harness."""

from upi_factory.agentic_code_generation.harness import (
    AGENT_ROLE_IDS,
    REQUIRED_ARTIFACTS,
    REQUIRED_LABELS,
    TOOL_IDS,
    generate_phase11a_artifacts,
    validate_phase11a_artifacts,
)

__all__ = [
    "AGENT_ROLE_IDS",
    "REQUIRED_ARTIFACTS",
    "REQUIRED_LABELS",
    "TOOL_IDS",
    "generate_phase11a_artifacts",
    "validate_phase11a_artifacts",
]
