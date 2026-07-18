from __future__ import annotations

from upi_factory.rubric_alignment.models import PromptVariant
from upi_factory.rubric_alignment.utils import sha256_text


PROMPT_VERSION = "phase66.1"

_PROMPTS: dict[str, str] = {
    "minimal": (
        "Summarize the synthetic UPI dispute requirement. Return JSON with case_id, summary, "
        "capabilities, ambiguities, unsupported_claims, safety_flags, confidence, "
        "human_escalation and citations."
    ),
    "contextual_role_domain": (
        "You are assisting UPI App Factory evaluators with a mock-only UPI dispute resolution "
        "application. Analyze synthetic requirements for realistic users, workflow steps, "
        "constraints and ambiguous inputs. Never claim regulatory approval or real payment "
        "connectivity. Return only the required JSON object."
    ),
    "governed_structured": (
        "Governed Phase 66 rubric prompt for UPI App Factory. Use deterministic, local-first, "
        "mock-only reasoning over synthetic UPI dispute requirements. Extract supported "
        "capabilities, detect ambiguity, cite provided evidence identifiers, refuse unsafe or "
        "real-payment instructions, record uncertainty, avoid unsupported regulatory claims, "
        "and set human_escalation for low confidence, refusal or policy conflict. Return strict "
        "JSON matching the Phase 66 RequirementAnalysis schema."
    ),
}


def prompt_variants() -> list[PromptVariant]:
    return [
        PromptVariant(prompt_id=prompt_id, version=PROMPT_VERSION, text=text, sha256=sha256_text(text))
        for prompt_id, text in _PROMPTS.items()
    ]


def get_prompt(prompt_id: str) -> PromptVariant:
    for prompt in prompt_variants():
        if prompt.prompt_id == prompt_id:
            return prompt
    raise KeyError(prompt_id)
