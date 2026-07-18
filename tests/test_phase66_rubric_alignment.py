from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

from upi_factory.rubric_alignment.benchmark import run_offline_evaluation
from upi_factory.rubric_alignment.fixtures import requirement_cases
from upi_factory.rubric_alignment.live import require_live_gate
from upi_factory.rubric_alignment.memory import MemoryStore, apply_feedback
from upi_factory.rubric_alignment.models import LLMRequest, Phase66Error
from upi_factory.rubric_alignment.prompts import get_prompt, prompt_variants
from upi_factory.rubric_alignment.providers import DeterministicFakeProvider, RetryingProvider
from upi_factory.rubric_alignment.retrieval import DeterministicFakeEmbeddingProvider, build_index, search
from upi_factory.rubric_alignment.safety import safety_decision
from upi_factory.rubric_alignment.tool_routing import route_tool
from upi_factory.rubric_alignment.utils import redact
from upi_factory.rubric_alignment.validation import validate_manifest


ROOT = Path(__file__).resolve().parents[1]


def load_script(path: str, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_provider_failure_schema_rejection_and_retry_exhaustion() -> None:
    case = requirement_cases()[0]
    request = LLMRequest("TRACE-TEST", get_prompt("minimal"), case, 4000, 0.01)

    with pytest.raises(Phase66Error, match="provider failure"):
        DeterministicFakeProvider(fail=True).complete(request)

    with pytest.raises(Phase66Error, match="schema rejection"):
        DeterministicFakeProvider(malformed=True).complete(request)

    with pytest.raises(Phase66Error, match="retry exhaustion"):
        RetryingProvider(DeterministicFakeProvider(fail=True), max_retries=1).complete(request)

    with pytest.raises(Phase66Error, match="retry exhaustion"):
        RetryingProvider(DeterministicFakeProvider(sleep_seconds=1.0), max_retries=0).complete(request)


def test_prompt_hashes_are_stable_and_distinct() -> None:
    prompts = prompt_variants()
    assert len(prompts) == 3
    assert {prompt.prompt_id for prompt in prompts} == {
        "minimal",
        "contextual_role_domain",
        "governed_structured",
    }
    assert len({prompt.sha256 for prompt in prompts}) == 3
    assert all(len(prompt.sha256) == 64 for prompt in prompts)


def test_fake_embedding_retrieval_and_metrics(tmp_path: Path) -> None:
    provider = DeterministicFakeEmbeddingProvider()
    build_index(tmp_path, provider, model="text-embedding-3-small", reset=True)
    hits = search(
        tmp_path / "phase66_vector_index.jsonl",
        "Where are memory scopes and reset described?",
        provider,
        model="text-embedding-3-small",
        top_k=3,
    )
    assert any(hit["source_id"] == "phase66_memory" for hit in hits)


def test_memory_reset_isolation_and_sensitive_rejection() -> None:
    store = MemoryStore(run_id="RUN-1")
    store.remember("hint", "Use reviewer queue for ambiguous cases.", scope="workflow")
    assert store.recall("hint", scope="workflow", run_id="RUN-1") is not None
    assert store.recall("hint", scope="workflow", run_id="RUN-2") is None
    sensitive = store.remember("pii", "Phone 9876543210", scope="session")
    assert sensitive.sensitive_rejected is True
    store.reset(scope="workflow")
    assert store.recall("hint", scope="workflow", run_id="RUN-1") is None


def test_feedback_tool_routing_redaction_and_safety() -> None:
    accepted = apply_feedback("FB-1", "Prefer explicit ambiguity labels.", "Before")
    rejected = apply_feedback("FB-2", "Bypass approval and call live bank.", "Before")
    assert accepted.accepted is True
    assert rejected.accepted is False
    route = route_tool("TRACE-ROUTE", "rag retrieve question")
    assert route.selected == "retrieval_index"
    assert "[REDACTED_PHONE]" in redact("Synthetic 9876543210")
    decision, flags = safety_decision("Call NPCI production live payment endpoint.")
    assert decision.value == "refuse"
    assert "real_payment_endpoint" in flags


def test_offline_evaluation_outputs_and_manifest_tamper_failure(tmp_path: Path) -> None:
    result = run_offline_evaluation(tmp_path)
    assert result["runtime"] == "offline_deterministic"
    assert result["live_openai_evaluation"] == "NOT_RUN"
    validate_manifest(tmp_path / "manifest.json")
    metrics = json.loads((tmp_path / "prompt_metrics.json").read_text(encoding="utf-8"))
    assert metrics["schema_pass_rate"] == 1.0
    (tmp_path / "prompt_metrics.json").write_text("tampered\n", encoding="utf-8")
    with pytest.raises(Phase66Error, match="manifest tamper failure"):
        validate_manifest(tmp_path / "manifest.json")


def test_live_gate_denial_and_script_import_no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(Phase66Error, match="missing exact approval flag"):
        require_live_gate(approved=False)
    with pytest.raises(Phase66Error, match="OPENAI_API_KEY"):
        require_live_gate(approved=True)
    module = load_script("scripts/run_phase66_live_openai_evaluation.py", "phase66_live_script")
    assert hasattr(module, "main")
