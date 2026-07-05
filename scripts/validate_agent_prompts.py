#!/usr/bin/env python3
"""Validate governed agent prompt pack completeness.

The validator is intentionally simple. It checks that the prompt manifest exists,
that every required role has a prompt file, and that each prompt contains the
core anti-hallucination, traceability, and beginner-debuggability terms.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PROMPT_ROOT = ROOT / "factory_governance" / "agent_prompts"
MANIFEST_PATH = PROMPT_ROOT / "agent_prompt_manifest.json"
COMMON_CONTRACT_PATH = PROMPT_ROOT / "common_governed_agent_contract.md"
GUIDE_PATH = ROOT / "docs" / "agent_prompt_quality_guide.md"

REQUIRED_AGENT_IDS = {
    "requirement_agent",
    "domain_agent",
    "architect_agent",
    "planner_agent",
    "developer_agent",
    "test_agent",
    "security_agent",
    "governance_agent",
    "evidence_agent",
    "reviewer_agent",
    "release_agent",
    "operations_agent",
    "regeneration_agent",
    "traceability_agent",
    "validation_agent",
}

REQUIRED_TERMS = [
    "Do not hallucinate",
    "MISSING_OFFICIAL_SOURCE",
    "MOCK_BOUNDARY",
    "SYNTHETIC_DATA",
    "requirement_ids",
    "task_ids",
    "policy_ids",
    "evidence_refs",
    "honesty_labels",
    "validation_commands",
    "beginner-readable",
    "debug",
    "If evidence is missing",
]


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file_handle:
        data = json.load(file_handle)
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return data


def validate() -> list[str]:
    errors: list[str] = []

    if not MANIFEST_PATH.exists():
        return [f"Missing prompt manifest: {MANIFEST_PATH}"]

    if not COMMON_CONTRACT_PATH.exists():
        errors.append(f"Missing common governed-agent contract: {COMMON_CONTRACT_PATH}")

    if not GUIDE_PATH.exists():
        errors.append(f"Missing agent prompt quality guide: {GUIDE_PATH}")

    try:
        manifest = load_json(MANIFEST_PATH)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [f"Unable to read prompt manifest: {exc}"]

    if manifest.get("schema_version") != "factory.agent_prompt_manifest.v1":
        errors.append("agent_prompt_manifest.json has an unexpected schema_version")

    agents = manifest.get("agents")
    if not isinstance(agents, list):
        return errors + ["agent_prompt_manifest.json must contain an agents list"]

    seen_agent_ids: set[str] = set()
    for item in agents:
        if not isinstance(item, dict):
            errors.append("Every manifest agent entry must be an object")
            continue

        agent_id = item.get("agent_id")
        prompt_file = item.get("prompt_file")
        if not isinstance(agent_id, str) or not agent_id:
            errors.append("Every agent entry must have a non-empty agent_id")
            continue
        if not isinstance(prompt_file, str) or not prompt_file:
            errors.append(f"Agent {agent_id} must have a non-empty prompt_file")
            continue

        seen_agent_ids.add(agent_id)
        prompt_path = PROMPT_ROOT / prompt_file
        if not prompt_path.exists():
            errors.append(f"Prompt file missing for {agent_id}: {prompt_path}")
            continue

        prompt_text = prompt_path.read_text(encoding="utf-8")
        for term in REQUIRED_TERMS:
            if term not in prompt_text:
                errors.append(f"Prompt {agent_id} is missing required term: {term}")

    missing_agents = sorted(REQUIRED_AGENT_IDS - seen_agent_ids)
    if missing_agents:
        errors.append("Missing required agent prompts: " + ", ".join(missing_agents))

    unknown_agents = sorted(seen_agent_ids - REQUIRED_AGENT_IDS)
    if unknown_agents:
        errors.append("Unknown agent prompts in manifest: " + ", ".join(unknown_agents))

    return errors


def main() -> int:
    errors = validate()
    result = {"errors": errors, "passed": not errors}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
