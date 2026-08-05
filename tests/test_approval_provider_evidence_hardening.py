from __future__ import annotations

import hashlib
import hmac
import json
import threading
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from factory.application_engineering.portfolio import (
    LOCAL_APPROVAL_TOKEN,
    PORTFOLIO_APPROVAL_TOKEN_ENV,
    ApprovalGrant as PortfolioApprovalGrant,
    PortfolioStore,
)
from factory.operator_portal.runtime_contracts import (
    ApprovalGrant as RuntimeApprovalGrant,
    RUNTIME_APPROVAL_TOKEN,
    RUNTIME_APPROVAL_TOKEN_ENV,
    scoped_approval_digest,
)
from factory.operator_portal.runtime_store import RuntimeStore
from factory.validators.validate_evidence_ledger import record_sha256, validate_evidence_ledger
from upi_factory.rubric_alignment.fixtures import requirement_cases
from upi_factory.rubric_alignment.models import LLMRequest, Phase66Error
from upi_factory.rubric_alignment.prompts import get_prompt
from upi_factory.rubric_alignment.providers import OpenAIResponsesProvider
from upi_factory.rubric_alignment.retrieval import OpenAIEmbeddingProvider


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_runtime_store_approval_mutations_are_serialized_under_concurrency(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(RUNTIME_APPROVAL_TOKEN_ENV, RUNTIME_APPROVAL_TOKEN)
    store = RuntimeStore(project_root=PROJECT_ROOT, state_root=tmp_path / "runtime")
    run_id = "phase50_race_guard"
    approvals_path = store.approvals_path(run_id)
    store.atomic_write_json(approvals_path, {"schema_version": "1.0", "approvals": []})

    first_read = threading.Event()
    second_read = threading.Event()
    release = threading.Event()
    original_read_json = store.read_json
    read_count = 0
    read_lock = threading.Lock()

    def guarded_read_json(path: Path) -> dict[str, Any]:
        nonlocal read_count
        payload = original_read_json(path)
        if path == approvals_path and threading.current_thread() is not threading.main_thread():
            with read_lock:
                read_count += 1
                current = read_count
            if current == 1:
                first_read.set()
                release.wait(1.0)
            elif current == 2:
                second_read.set()
                release.wait(1.0)
        return payload

    monkeypatch.setattr(store, "read_json", guarded_read_json)

    def approval(nonce: str) -> RuntimeApprovalGrant:
        approved_at = datetime.now(timezone.utc).replace(microsecond=0)
        return RuntimeApprovalGrant(
            run_id=run_id,
            action="start",
            nonce=nonce,
            approved_at_utc=approved_at.isoformat().replace("+00:00", "Z"),
            expires_at_utc=(approved_at + timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
            token_sha256=scoped_approval_digest(
                run_id=run_id,
                action="start",
                nonce=nonce,
                token=RUNTIME_APPROVAL_TOKEN,
            ),
        )

    left = threading.Thread(target=store.create_approval, args=(approval("nonce-left"),))
    right = threading.Thread(target=store.create_approval, args=(approval("nonce-right"),))
    left.start()
    assert first_read.wait(1.0)
    right.start()
    assert not second_read.wait(0.1)
    release.set()
    left.join()
    right.join()
    approvals = json.loads(approvals_path.read_text(encoding="utf-8"))
    assert {item["nonce"] for item in approvals["approvals"]} == {"nonce-left", "nonce-right"}

    consume_first = threading.Event()
    consume_second = threading.Event()
    consume_release = threading.Event()
    consume_count = 0

    def guarded_consume_read(path: Path) -> dict[str, Any]:
        nonlocal consume_count
        payload = original_read_json(path)
        if path == approvals_path and threading.current_thread() is not threading.main_thread():
            with read_lock:
                consume_count += 1
                current = consume_count
            if current == 1:
                consume_first.set()
                consume_release.wait(1.0)
            elif current == 2:
                consume_second.set()
                consume_release.wait(1.0)
        return payload

    monkeypatch.setattr(store, "read_json", guarded_consume_read)
    results: list[str] = []

    def consume() -> None:
        try:
            store.consume_approval(run_id=run_id, action="start", nonce="nonce-left")
            results.append("consumed")
        except Exception as exc:  # pragma: no cover - assertion below inspects exact class
            results.append(type(exc).__name__)

    first = threading.Thread(target=consume)
    second = threading.Thread(target=consume)
    first.start()
    assert consume_first.wait(1.0)
    second.start()
    assert not consume_second.wait(0.1)
    consume_release.set()
    first.join()
    second.join()
    assert results.count("consumed") == 1
    assert results.count("RuntimeContractError") == 1


def test_portfolio_approval_mutations_are_serialized_under_concurrency(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(PORTFOLIO_APPROVAL_TOKEN_ENV, LOCAL_APPROVAL_TOKEN)
    store = PortfolioStore(project_root=PROJECT_ROOT, state_root=tmp_path / "portfolio")
    store.atomic_write_json(store.approvals_path, {"schema_version": "1.0", "approvals": []})
    approvals_path = store.approvals_path

    first_read = threading.Event()
    second_read = threading.Event()
    release = threading.Event()
    original_read_json = store.read_json
    read_count = 0
    read_lock = threading.Lock()

    def guarded_read_json(path: Path) -> dict[str, Any]:
        nonlocal read_count
        payload = original_read_json(path)
        if path == approvals_path and threading.current_thread() is not threading.main_thread():
            with read_lock:
                read_count += 1
                current = read_count
            if current == 1:
                first_read.set()
                release.wait(1.0)
            elif current == 2:
                second_read.set()
                release.wait(1.0)
        return payload

    monkeypatch.setattr(store, "read_json", guarded_read_json)

    approved_at = datetime.now(timezone.utc).replace(microsecond=0)
    base_grant = PortfolioApprovalGrant(
        action="start",
        scope="runtime-1",
        nonce="nonce-portfolio-left",
        actor="operator",
        approved_at_utc=approved_at.isoformat().replace("+00:00", "Z"),
        expires_at_utc=(approved_at + timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
        token_sha256="placeholder",
    )
    left = replace(
        base_grant,
        token_sha256=hmac.new(
            LOCAL_APPROVAL_TOKEN.encode("utf-8"),
            b"start:runtime-1:nonce-portfolio-left",
            hashlib.sha256,
        ).hexdigest(),
    )
    right = replace(
        base_grant,
        nonce="nonce-portfolio-right",
        token_sha256=hmac.new(
            LOCAL_APPROVAL_TOKEN.encode("utf-8"),
            b"start:runtime-1:nonce-portfolio-right",
            hashlib.sha256,
        ).hexdigest(),
    )

    thread_left = threading.Thread(target=store.create_approval, args=(left,))
    thread_right = threading.Thread(target=store.create_approval, args=(right,))
    thread_left.start()
    assert first_read.wait(1.0)
    thread_right.start()
    assert not second_read.wait(0.1)
    release.set()
    thread_left.join()
    thread_right.join()
    approvals = json.loads(approvals_path.read_text(encoding="utf-8"))
    assert {item["nonce"] for item in approvals["approvals"]} == {
        "nonce-portfolio-left",
        "nonce-portfolio-right",
    }

    consume_first = threading.Event()
    consume_second = threading.Event()
    consume_release = threading.Event()
    consume_count = 0

    def guarded_consume_read(path: Path) -> dict[str, Any]:
        nonlocal consume_count
        payload = original_read_json(path)
        if path == approvals_path and threading.current_thread() is not threading.main_thread():
            with read_lock:
                consume_count += 1
                current = consume_count
            if current == 1:
                consume_first.set()
                consume_release.wait(1.0)
            elif current == 2:
                consume_second.set()
                consume_release.wait(1.0)
        return payload

    monkeypatch.setattr(store, "read_json", guarded_consume_read)
    results: list[str] = []

    def consume() -> None:
        try:
            store.consume_approval(action="start", scope="runtime-1", nonce="nonce-portfolio-left")
            results.append("consumed")
        except Exception as exc:  # pragma: no cover - assertion below inspects exact class
            results.append(type(exc).__name__)

    first_consumer = threading.Thread(target=consume)
    second_consumer = threading.Thread(target=consume)
    first_consumer.start()
    assert consume_first.wait(1.0)
    second_consumer.start()
    assert not consume_second.wait(0.1)
    consume_release.set()
    first_consumer.join()
    second_consumer.join()
    assert results.count("consumed") == 1
    assert results.count("PortfolioError") == 1


def test_live_provider_boundary_fails_closed_at_provider_entrypoints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("UPI_APP_FACTORY_ALLOW_LIVE_OPENAI", raising=False)
    case = requirement_cases()[0]
    request = LLMRequest("TRACE-LIVE-BOUNDARY", get_prompt("minimal"), case, 4000, 0.01)

    with pytest.raises(Phase66Error, match="missing exact approval flag"):
        OpenAIResponsesProvider(model="gpt-test").complete(request)
    with pytest.raises(Phase66Error, match="missing exact approval flag"):
        OpenAIEmbeddingProvider().embed(["synthetic"], model="text-embedding-3-small", trace_id="TRACE")

    monkeypatch.setenv("UPI_APP_FACTORY_ALLOW_LIVE_OPENAI", "1")
    with pytest.raises(Phase66Error, match="OPENAI_API_KEY"):
        OpenAIResponsesProvider(model="gpt-test").complete(request)
    with pytest.raises(Phase66Error, match="OPENAI_API_KEY"):
        OpenAIEmbeddingProvider().embed(["synthetic"], model="text-embedding-3-small", trace_id="TRACE")



def _require_record_sha256_link(value: object) -> str:
    """Runtime-check a hash-chain link before hashing it."""
    assert isinstance(value, str)
    return value

def test_evidence_ledger_validator_checks_hash_chain_duplicates_and_artifacts(
    tmp_path: Path,
) -> None:
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir(parents=True)
    artifact = artifact_root / "case.txt"
    artifact.write_text("synthetic evidence artifact\n", encoding="utf-8")
    ledger_path = tmp_path / "evidence" / "evidence_ledger.jsonl"
    ledger_path.parent.mkdir(parents=True)

    first = {
        "sequence": 1,
        "evidence_id": "EVID-001",
        "source_type": "TEST",
        "title": "First record",
        "status": "ACTIVE",
        "artifacts": [{"path": "artifacts/case.txt", "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest()}],
    }
    first["previous_record_sha256"] = "0" * 64
    first["record_sha256"] = record_sha256(first, _require_record_sha256_link(first["previous_record_sha256"]))
    second = {
        "sequence": 2,
        "evidence_id": "EVID-002",
        "source_type": "TEST",
        "title": "Second record",
        "status": "ACTIVE",
        "artifacts": [],
    }
    second["previous_record_sha256"] = first["record_sha256"]
    second["record_sha256"] = record_sha256(second, _require_record_sha256_link(second["previous_record_sha256"]))
    ledger_path.write_text(
        json.dumps(first, sort_keys=True) + "\n" + json.dumps(second, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    passed = validate_evidence_ledger(ledger_path)
    assert passed["passed"] is True
    assert passed["verified_records"] == 2

    second["evidence_id"] = "EVID-001"
    ledger_path.write_text(
        json.dumps(first, sort_keys=True) + "\n" + json.dumps(second, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    failed = validate_evidence_ledger(ledger_path)
    assert failed["passed"] is False
    assert any("duplicate evidence_id" in error for error in failed["errors"])
