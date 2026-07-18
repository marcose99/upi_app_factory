from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from upi_factory.rubric_alignment.benchmark import run_prompt_benchmark
from upi_factory.rubric_alignment.fixtures import retrieval_questions
from upi_factory.rubric_alignment.metrics import retrieval_metrics
from upi_factory.rubric_alignment.models import Phase66Error
from upi_factory.rubric_alignment.providers import OpenAIResponsesProvider
from upi_factory.rubric_alignment.retrieval import (
    OpenAIEmbeddingProvider,
    build_index,
    retrieval_answer,
    search,
)
from upi_factory.rubric_alignment.utils import project_root, sha256_file, write_json


def require_live_gate(*, approved: bool) -> None:
    if not approved:
        raise Phase66Error("live OpenAI evaluation denied: missing exact approval flag")
    if not os.environ.get("OPENAI_API_KEY"):
        raise Phase66Error("live OpenAI evaluation denied: OPENAI_API_KEY is not present")


def run_live_openai_evaluation(output_root: Path, *, approved: bool, llm_model: str, embedding_model: str, max_llm_calls: int) -> dict[str, Any]:
    require_live_gate(approved=approved)
    if max_llm_calls > 45:
        raise Phase66Error("max_llm_calls must be at or below 45")
    output_root.mkdir(parents=True, exist_ok=True)
    prompt_metrics = run_prompt_benchmark(
        output_root,
        OpenAIResponsesProvider(model=llm_model),
        max_llm_calls=max_llm_calls,
    )
    embedding_provider = OpenAIEmbeddingProvider()
    retrieval_manifest = build_index(
        output_root,
        embedding_provider,
        model=embedding_model,
        reset=True,
    )
    retrieval_rows: list[dict[str, Any]] = []
    for question in retrieval_questions():
        hits = search(
            output_root / "phase66_vector_index.jsonl",
            question.question,
            embedding_provider,
            model=embedding_model,
            top_k=3,
        )
        retrieval_rows.append(
            {
                "question_id": question.question_id,
                "expected_source_ids": question.expected_source_ids,
                "retrieved_source_ids": [hit["source_id"] for hit in hits],
                "rag_answer": retrieval_answer(question.question, hits),
                "no_rag_answer": {"answer": "No corpus citations used.", "citations": []},
            }
        )
    retrieval_result = {
        "manifest": retrieval_manifest,
        "metrics": retrieval_metrics(retrieval_rows, top_k=3),
        "results": retrieval_rows,
    }
    write_json(output_root / "retrieval_results.json", retrieval_result)
    manifest = {
        "runtime": "guarded_live_openai",
        "llm_model_requested": llm_model,
        "embedding_model_requested": embedding_model,
        "max_llm_calls": max_llm_calls,
        "prompt_metrics": prompt_metrics,
        "retrieval_metrics": retrieval_result,
    }
    write_json(output_root / "manifest.json", manifest)
    files = sorted(
        path
        for path in output_root.rglob("*")
        if path.is_file() and path.name not in {"manifest.json", "SHA256SUMS"}
    )
    (output_root / "SHA256SUMS").write_text(
        "\n".join(f"{sha256_file(path)}  {path.relative_to(output_root).as_posix()}" for path in files)
        + "\n",
        encoding="utf-8",
    )
    summary_path = project_root() / "docs" / "capstone" / "phase66" / "phase66_evaluation_summary.md"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        "\n".join(
            [
                "# Phase 66 Evaluation Summary",
                "",
                "Guarded live OpenAI evaluation executed with sanitized evidence.",
                f"Requested LLM model: `{llm_model}`.",
                f"Requested embedding model: `{embedding_model}`.",
                "This evidence does not claim production readiness, certification or a perfect rubric score.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return manifest
