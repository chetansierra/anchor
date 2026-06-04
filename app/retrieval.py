"""Query-time retrieval: embed the query, cosine-search the store, return hits."""
from __future__ import annotations

import time

from .config import Settings
from .embeddings import Embedder, build_embedder
from .vectorstore import LocalVectorStore, SearchHit


class Retriever:
    def __init__(self, store: LocalVectorStore, embedder: Embedder) -> None:
        self.store = store
        self.embedder = embedder

    @classmethod
    def load(cls, settings: Settings, embedder: Embedder | None = None) -> "Retriever":
        store = LocalVectorStore.load(settings.index_path)
        emb: Embedder = embedder if embedder is not None else build_embedder(settings)
        if emb.dim != store.dim:
            raise RuntimeError(
                f"Embedder '{emb.name}' (dim {emb.dim}) does not match the index "
                f"(dim {store.dim}). Re-run ingestion after changing EMBEDDER."
            )
        return cls(store, emb)

    def search(self, query: str, k: int) -> tuple[list[SearchHit], float]:
        started = time.perf_counter()
        query_vector = self.embedder.embed_query(query)
        hits = self.store.search(query_vector, k)
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        return hits, latency_ms
