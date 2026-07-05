"""Prompt loading helpers for governed role-agent simulations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from factory.agents.contracts import AGENT_SEQUENCE

PROMPT_ROOT = Path("factory_governance/agent_prompts")
PROMPT_DIR = PROMPT_ROOT / "prompts"
PROMPT_MANIFEST = PROMPT_ROOT / "agent_prompt_manifest.json"
COMMON_CONTRACT = PROMPT_ROOT / "common_governed_agent_contract.md"


class PromptPackError(RuntimeError):
    """Raised when the governed prompt pack is missing or incomplete."""


def read_text_file(path: Path) -> str:
    """Read UTF-8 text with an actionable error message."""

    if not path.exists():
        raise PromptPackError(f"Required prompt-pack file is missing: {path}")
    return path.read_text(encoding="utf-8")


def load_prompt_pack_manifest(project_root: Path) -> dict[str, Any]:
    """Load the governed agent prompt manifest."""

    manifest_path = project_root / PROMPT_MANIFEST
    raw_text = read_text_file(manifest_path)
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise PromptPackError(f"Prompt manifest is invalid JSON: {manifest_path}") from exc
    if not isinstance(data, dict):
        raise PromptPackError("Prompt manifest must be a JSON object.")
    return cast(dict[str, Any], data)


def prompt_path_for_agent(project_root: Path, agent_id: str) -> Path:
    """Return the prompt file path for one agent."""

    return project_root / PROMPT_DIR / f"{agent_id}.md"


def load_agent_prompt(project_root: Path, agent_id: str) -> str:
    """Load one role-agent prompt."""

    if agent_id not in AGENT_SEQUENCE:
        raise PromptPackError(f"Unknown governed agent: {agent_id}")
    return read_text_file(prompt_path_for_agent(project_root, agent_id))


def validate_prompt_pack_files(project_root: Path) -> list[str]:
    """Return prompt-pack file errors without raising.

    This function is intentionally simple so failures are easy to debug.
    """

    errors: list[str] = []
    required_files = [project_root / PROMPT_MANIFEST, project_root / COMMON_CONTRACT]
    required_files.extend(prompt_path_for_agent(project_root, agent) for agent in AGENT_SEQUENCE)

    for path in required_files:
        if not path.exists():
            errors.append(f"Missing required prompt-pack file: {path}")
    return errors
