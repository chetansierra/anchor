"""Ingestion pipeline: load -> chunk -> embed -> upsert -> persist.

This is the function behind both the `/ingest` endpoint and the CLI. Re-running
it rebuilds the index from scratch (idempotent), which is exactly the per-client
onboarding step we'll reuse later.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

from .chunking import build_token_counter, chunk_text
from .config import Settings
from .embeddings import Embedder, build_embedder
from .kb_loader import load_documents
from .vectorstore import ChunkRecord, LocalVectorStore


@dataclass
class IngestStats:
    documents: int
    chunks: int
    embedder: str
    dim: int
    elapsed_ms: float


def run_ingest(settings: Settings, embedder: Embedder | None = None) -> IngestStats:
    started = time.perf_counter()
    emb: Embedder = embedder if embedder is not None else build_embedder(settings)
    count_tokens = build_token_counter(settings.chars_per_token)

    documents = load_documents(settings.kb_path)

    records: list[ChunkRecord] = []
    texts: list[str] = []
    for doc in documents:
        chunks = chunk_text(
            doc.text,
            target_tokens=settings.chunk_target_tokens,
            overlap_tokens=settings.chunk_overlap_tokens,
            count_tokens=count_tokens,
        )
        for ch in chunks:
            records.append(
                ChunkRecord(
                    id=f"{doc.doc_id}::{ch.index}",
                    doc_id=doc.doc_id,
                    title=doc.title,
                    source=doc.source,
                    chunk_index=ch.index,
                    text=ch.text,
                )
            )
            texts.append(ch.text)

    vectors = emb.embed_documents(texts)

    store = LocalVectorStore(settings.index_path, emb.name, emb.dim)
    store.upsert(vectors, records)
    store.save()

    return IngestStats(
        documents=len(documents),
        chunks=len(records),
        embedder=emb.name,
        dim=emb.dim,
        elapsed_ms=round((time.perf_counter() - started) * 1000, 1),
    )
