"""Query-time retrieval: embed the query, cosine-search the store, return hits."""
from __future__ import annotations

import time
from pathlib import Path

from .config import Settings
from .embeddings import Embedder, build_embedder
from .vectorstore import LocalVectorStore, SearchHit


class Retriever:
    def __init__(self, store: LocalVectorStore, embedder: Embedder) -> None:
        self.store = store
        self.embedder = embedder

    @classmethod
    def load(
        cls,
        settings: Settings,
        embedder: Embedder | None = None,
        index_path: Path | None = None,
    ) -> "Retriever":
        """Load a retriever over a persisted index. Defaults to the Nimbus
        support index; pass ``index_path`` (e.g. ``settings.services_index_path``)
        to load the consultant's services corpus instead."""
        store = LocalVectorStore.load(index_path or settings.index_path)
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
