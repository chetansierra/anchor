"""Pydantic request/response schemas for the API."""
from __future__ import annotations

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    business: str
    embedder: str | None = None
    indexed_chunks: int = 0
    indexed_documents: int = 0


class IngestResponse(BaseModel):
    documents: int
    chunks: int
    embedder: str
    dim: int
    elapsed_ms: float


class RetrievedChunk(BaseModel):
    doc_id: str
    title: str
    source: str
    chunk_index: int
    score: float = Field(description="Cosine similarity in [-1, 1].")
    text: str


class QueryRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int | None = Field(default=None, ge=1, le=20)


class QueryResponse(BaseModel):
    query: str
    embedder: str
    latency_ms: float
    results: list[RetrievedChunk]
