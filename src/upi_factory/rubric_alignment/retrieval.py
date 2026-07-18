from __future__ import annotations

import math
from dataclasses import asdict
from pathlib import Path

from upi_factory.rubric_alignment.fixtures import corpus_documents
from upi_factory.rubric_alignment.models import DocumentChunk, EmbeddingProvider, Phase66Error
from upi_factory.rubric_alignment.utils import sha256_text, write_json, write_jsonl


class DeterministicFakeEmbeddingProvider:
    provider_name = "deterministic_fake_embeddings"

    def embed(self, texts: list[str], *, model: str, trace_id: str) -> list[list[float]]:
        return [_embed_text(text) for text in texts]


class OpenAIEmbeddingProvider:
    provider_name = "openai_embeddings"

    def embed(self, texts: list[str], *, model: str, trace_id: str) -> list[list[float]]:
        try:
            from openai import OpenAI
        except ImportError as error:
            raise Phase66Error("openai SDK is required for live embeddings") from error
        response = OpenAI(timeout=30.0, max_retries=1).embeddings.create(model=model, input=texts)
        returned = [list(item.embedding) for item in response.data]
        if len(returned) != len(texts):
            raise Phase66Error("embedding response count mismatch")
        return returned


def _embed_text(text: str) -> list[float]:
    buckets = [0.0] * 32
    for raw in text.lower().replace("-", " ").split():
        token = "".join(ch for ch in raw if ch.isalnum())
        if token:
            buckets[int(sha256_text(token)[:8], 16) % len(buckets)] += 1.0
    norm = math.sqrt(sum(value * value for value in buckets)) or 1.0
    return [value / norm for value in buckets]


def cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise Phase66Error("embedding dimension mismatch")
    return sum(a * b for a, b in zip(left, right)) / ((math.sqrt(sum(a * a for a in left)) or 1.0) * (math.sqrt(sum(b * b for b in right)) or 1.0))


def build_chunks() -> list[DocumentChunk]:
    chunks: list[DocumentChunk] = []
    for source_id, text in sorted(corpus_documents().items()):
        chunks.append(DocumentChunk(source_id=source_id, chunk_id=f"{source_id}:0001", text=text, sha256=sha256_text(text), metadata={"approved": "true", "synthetic": "true"}))
    return chunks


def build_index(output_dir: Path, provider: EmbeddingProvider, *, model: str, reset: bool = False) -> dict[str, object]:
    if reset and output_dir.exists():
        for path in output_dir.glob("phase66_vector_index*"):
            path.unlink()
    chunks = build_chunks()
    embeddings = provider.embed([chunk.text for chunk in chunks], model=model, trace_id="TRACE-P66-EMBED-001")
    rows = [{"chunk": asdict(chunk), "embedding": embedding} for chunk, embedding in zip(chunks, embeddings)]
    manifest = {"model": model, "provider": provider.provider_name, "chunk_count": len(chunks), "corpus_sha256": sha256_text("".join(chunk.sha256 for chunk in chunks))}
    write_jsonl(output_dir / "phase66_vector_index.jsonl", rows)
    write_json(output_dir / "phase66_corpus_manifest.json", manifest)
    return manifest


def search(index_path: Path, question: str, provider: EmbeddingProvider, *, model: str, top_k: int) -> list[dict[str, object]]:
    import json

    rows = [json.loads(line) for line in index_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    query_embedding = provider.embed([question], model=model, trace_id="TRACE-P66-SEARCH-001")[0]
    scored = [
        {"source_id": row["chunk"]["source_id"], "chunk_id": row["chunk"]["chunk_id"], "score": cosine(query_embedding, row["embedding"]), "text": row["chunk"]["text"]}
        for row in rows
    ]
    return sorted(scored, key=lambda row: float(row["score"]), reverse=True)[:top_k]


def _hit_score(hit: dict[str, object]) -> float:
    score = hit["score"]
    if not isinstance(score, (int, float)):
        raise Phase66Error("retrieval hit score must be numeric")
    return float(score)


def retrieval_answer(question: str, hits: list[dict[str, object]]) -> dict[str, object]:
    citations = [str(hit["source_id"]) for hit in hits if _hit_score(hit) > 0.05]
    if not citations:
        return {"answer": "No supported answer from the approved Phase 66 corpus.", "citations": [], "human_review": True}
    return {"answer": f"Supported by approved Phase 66 sources: {', '.join(citations)}.", "citations": citations, "human_review": False}
