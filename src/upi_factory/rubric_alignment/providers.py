from __future__ import annotations

import json
import os
import time
from dataclasses import asdict
from typing import Any, cast

from upi_factory.rubric_alignment.models import (
    LLMProvider,
    LLMRequest,
    LLMResponse,
    Phase66Error,
    Usage,
)
from upi_factory.rubric_alignment.safety import safety_decision
from upi_factory.rubric_alignment.schema import validate_analysis


class DeterministicFakeProvider:
    provider_name = "deterministic_fake"

    def __init__(self, *, fail: bool = False, malformed: bool = False, sleep_seconds: float = 0.0) -> None:
        self.fail = fail
        self.malformed = malformed
        self.sleep_seconds = sleep_seconds

    def complete(self, request: LLMRequest) -> LLMResponse:
        started = time.perf_counter()
        if self.sleep_seconds > request.timeout_seconds:
            raise TimeoutError("provider timeout exceeded")
        if self.sleep_seconds:
            time.sleep(self.sleep_seconds)
        if self.fail:
            raise Phase66Error("provider failure injected")
        decision, flags = safety_decision(request.case.input_text)
        lower = request.case.input_text.lower()
        capabilities = [
            capability
            for capability in request.case.expected_capabilities
            if capability.replace("_", " ") in lower or capability in request.case.expected_capabilities
        ]
        ambiguities = ["missing_dispute_time_window"] if request.case.ambiguous else []
        unsupported = ["regulatory_certification_claim"] if "rbi certified" in lower else []
        confidence = 0.58 if request.case.ambiguous else 0.86
        payload: dict[str, Any] = {
            "case_id": request.case.case_id,
            "summary": f"Synthetic analysis for {request.case.title}.",
            "capabilities": capabilities,
            "ambiguities": ambiguities,
            "unsupported_claims": unsupported,
            "safety_flags": flags,
            "confidence": confidence,
            "human_escalation": bool(flags or ambiguities or confidence < 0.65 or decision.value != "allow"),
            "citations": [f"fixture:{request.case.case_id}"],
        }
        if self.malformed:
            payload.pop("confidence")
        analysis = validate_analysis(payload)
        return LLMResponse(
            analysis=analysis,
            raw_text=json.dumps(payload, sort_keys=True),
            schema_valid=True,
            latency_ms=(time.perf_counter() - started) * 1000,
            usage=Usage(input_tokens=len(request.case.input_text.split()), output_tokens=60, total_tokens=60 + len(request.case.input_text.split())),
            model_returned="deterministic-fake-phase66",
            refusal=decision.value == "refuse",
        )


class RetryingProvider:
    def __init__(self, provider: LLMProvider, *, max_retries: int) -> None:
        self.provider = provider
        self.max_retries = max_retries
        self.provider_name = f"retrying_{provider.provider_name}"

    def complete(self, request: LLMRequest) -> LLMResponse:
        last_error: Exception | None = None
        for _attempt in range(self.max_retries + 1):
            try:
                return self.provider.complete(request)
            except (Phase66Error, TimeoutError) as error:
                last_error = error
        raise Phase66Error(f"retry exhaustion: {last_error}") from last_error


class OpenAIResponsesProvider:
    provider_name = "openai_responses"

    def __init__(
        self,
        *,
        model: str,
        timeout_seconds: float = 30.0,
        max_retries: int = 1,
        live_approved: bool = False,
    ) -> None:
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.live_approved = live_approved

    def complete(self, request: LLMRequest) -> LLMResponse:
        if len(request.case.input_text) > request.max_input_chars:
            raise Phase66Error("input bound exceeded")
        require_live_provider_boundary(
            live_approved=self.live_approved,
            missing_flag_message="live OpenAI evaluation denied: missing exact approval flag",
            missing_key_message="live OpenAI evaluation denied: OPENAI_API_KEY is not present",
        )
        try:
            from openai import OpenAI
        except ImportError as error:
            raise Phase66Error("openai SDK is required for live evaluation") from error
        client = OpenAI(timeout=min(self.timeout_seconds, request.timeout_seconds), max_retries=self.max_retries)
        started = time.perf_counter()
        response = client.responses.create(
            model=self.model,
            input=[
                {"role": "system", "content": request.prompt.text},
                {"role": "user", "content": request.case.input_text},
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "phase66_requirement_analysis",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": [
                            "case_id",
                            "summary",
                            "capabilities",
                            "ambiguities",
                            "unsupported_claims",
                            "safety_flags",
                            "confidence",
                            "human_escalation",
                            "citations",
                        ],
                        "properties": {
                            "case_id": {"type": "string"},
                            "summary": {"type": "string"},
                            "capabilities": {"type": "array", "items": {"type": "string"}},
                            "ambiguities": {"type": "array", "items": {"type": "string"}},
                            "unsupported_claims": {"type": "array", "items": {"type": "string"}},
                            "safety_flags": {"type": "array", "items": {"type": "string"}},
                            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                            "human_escalation": {"type": "boolean"},
                            "citations": {"type": "array", "items": {"type": "string"}},
                        },
                    },
                }
            },
        )
        raw_text = str(getattr(response, "output_text", ""))
        payload = cast(dict[str, Any], json.loads(raw_text))
        analysis = validate_analysis(payload)
        usage_obj = getattr(response, "usage", None)
        usage = Usage(
            input_tokens=int(getattr(usage_obj, "input_tokens", 0) or 0),
            output_tokens=int(getattr(usage_obj, "output_tokens", 0) or 0),
            total_tokens=int(getattr(usage_obj, "total_tokens", 0) or 0),
        )
        return LLMResponse(
            analysis=analysis,
            raw_text=raw_text,
            schema_valid=True,
            latency_ms=(time.perf_counter() - started) * 1000,
            usage=usage,
            model_returned=str(getattr(response, "model", self.model)),
            refusal=bool(getattr(response, "refusal", False)),
        )


def response_to_dict(response: LLMResponse) -> dict[str, Any]:
    payload = asdict(response)
    payload["raw_text_sha256"] = __import__("hashlib").sha256(response.raw_text.encode("utf-8")).hexdigest()
    payload.pop("raw_text", None)
    return payload


def require_live_provider_boundary(
    *,
    live_approved: bool,
    missing_flag_message: str,
    missing_key_message: str,
) -> None:
    if not live_approved and os.environ.get("UPI_APP_FACTORY_ALLOW_LIVE_OPENAI") != "1":
        raise Phase66Error(missing_flag_message)
    if not os.environ.get("OPENAI_API_KEY"):
        raise Phase66Error(missing_key_message)
