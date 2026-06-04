"""FastAPI app: /health, /ingest, /query.

Day 1 exposes raw retrieval so we can prove the RAG foundation works before the
agent layer lands in Day 2. The index is loaded once at startup (if present) and
refreshed after every /ingest.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from . import __version__
from .config import get_settings
from .ingest import run_ingest
from .models import (
    HealthResponse,
    IngestResponse,
    QueryRequest,
    QueryResponse,
    RetrievedChunk,
)
from .retrieval import Retriever
from .vectorstore import LocalVectorStore

# Simple module-level holder for the loaded retriever (single-process demo).
_state: dict[str, Retriever | None] = {"retriever": None}


def _load_retriever_safely() -> Retriever | None:
    settings = get_settings()
    if not LocalVectorStore.exists(settings.index_path):
        return None
    try:
        return Retriever.load(settings)
    except Exception:
        # Stale/incompatible index — surfaced via /health; /ingest fixes it.
        return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    _state["retriever"] = _load_retriever_safely()
    yield


app = FastAPI(title="Nimbus Support Agent", version=__version__, lifespan=lifespan)


@app.get("/", include_in_schema=False)
def root() -> dict:
    return {
        "service": "Nimbus Support Agent",
        "version": __version__,
        "endpoints": ["/health", "/ingest", "/query", "/docs"],
    }


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    retriever = _state["retriever"]
    if retriever is None:
        return HealthResponse(
            status="ok", business=settings.business_name, embedder=None
        )
    return HealthResponse(
        status="ok",
        business=settings.business_name,
        embedder=retriever.embedder.name,
        indexed_chunks=retriever.store.count,
        indexed_documents=retriever.store.n_documents,
    )


@app.post("/ingest", response_model=IngestResponse)
def ingest() -> IngestResponse:
    settings = get_settings()
    try:
        stats = run_ingest(settings)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    _state["retriever"] = _load_retriever_safely()
    return IngestResponse(
        documents=stats.documents,
        chunks=stats.chunks,
        embedder=stats.embedder,
        dim=stats.dim,
        elapsed_ms=stats.elapsed_ms,
    )


@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest) -> QueryResponse:
    settings = get_settings()
    retriever = _state["retriever"]
    if retriever is None:
        raise HTTPException(
            status_code=409,
            detail="No index loaded. POST /ingest first to build the KB index.",
        )
    k = req.top_k or settings.top_k
    hits, latency_ms = retriever.search(req.query, k)
    return QueryResponse(
        query=req.query,
        embedder=retriever.embedder.name,
        latency_ms=latency_ms,
        results=[
            RetrievedChunk(
                doc_id=h.record.doc_id,
                title=h.record.title,
                source=h.record.source,
                chunk_index=h.record.chunk_index,
                score=round(h.score, 4),
                text=h.record.text,
            )
            for h in hits
        ],
    )
