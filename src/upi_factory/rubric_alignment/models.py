from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal, Protocol


APP_ID = "upi_dispute_resolution"
PRODUCT_ID = "upi_app_factory"
PRODUCT_NAME = "UPI App Factory"
PHASE_ID = "phase66_rubric_alignment"


class Phase66Error(RuntimeError):
    """Fail-closed Phase 66 error."""


class SafetyDecision(str, Enum):
    ALLOW = "allow"
    REFUSE = "refuse"
    ESCALATE = "escalate"


@dataclass(frozen=True)
class PromptVariant:
    prompt_id: str
    version: str
    text: str
    sha256: str


@dataclass(frozen=True)
class RequirementCase:
    case_id: str
    title: str
    input_text: str
    expected_capabilities: list[str]
    ambiguous: bool
    forbidden_topics: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class LLMRequest:
    trace_id: str
    prompt: PromptVariant
    case: RequirementCase
    max_input_chars: int
    timeout_seconds: float


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


@dataclass(frozen=True)
class RequirementAnalysis:
    case_id: str
    summary: str
    capabilities: list[str]
    ambiguities: list[str]
    unsupported_claims: list[str]
    safety_flags: list[str]
    confidence: float
    human_escalation: bool
    citations: list[str]


@dataclass(frozen=True)
class LLMResponse:
    analysis: RequirementAnalysis
    raw_text: str
    schema_valid: bool
    latency_ms: float
    usage: Usage
    model_returned: str
    refusal: bool = False


class LLMProvider(Protocol):
    provider_name: str

    def complete(self, request: LLMRequest) -> LLMResponse: ...


class EmbeddingProvider(Protocol):
    provider_name: str

    def embed(self, texts: list[str], *, model: str, trace_id: str) -> list[list[float]]: ...


@dataclass(frozen=True)
class DocumentChunk:
    source_id: str
    chunk_id: str
    text: str
    sha256: str
    metadata: dict[str, str]


@dataclass(frozen=True)
class RetrievalQuestion:
    question_id: str
    question: str
    expected_source_ids: list[str]
    irrelevant_source_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ToolRoute:
    trace_id: str
    considered: list[str]
    selected: str
    rejected: dict[str, str]
    reason: str


MemoryScope = Literal["session", "workflow", "evidence"]


@dataclass(frozen=True)
class MemoryRecord:
    key: str
    value: str
    scope: MemoryScope
    expires_after_runs: int
    created_run_id: str
    sensitive_rejected: bool = False


@dataclass(frozen=True)
class ReviewerFeedback:
    feedback_id: str
    text: str
    accepted: bool
    rejected_reason: str | None
    before: str
    after: str


JsonDict = dict[str, Any]
