"""Pydantic request/response schemas for the API."""
from __future__ import annotations

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    business: str
    embedder: str | None = None
    indexed_chunks: int = 0
    indexed_documents: int = 0
    provider: str | None = None
    model: str | None = None


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


# --- Day 2: agent /chat ------------------------------------------------------


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    top_k: int | None = Field(default=None, ge=1, le=20)


class Citation(BaseModel):
    n: int
    doc_id: str
    title: str
    source: str
    score: float


class RetrievedSource(BaseModel):
    rank: int
    doc_id: str
    title: str
    source: str
    score: float
    text: str


class ToolCallInfo(BaseModel):
    name: str
    arguments: dict
    result: str


class UsageInfo(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0


class ChatResponse(BaseModel):
    answer: str
    grounded: bool
    escalated: bool
    citations: list[Citation] = []
    tool_calls: list[ToolCallInfo] = []
    retrieved: list[RetrievedSource] = []
    usage: UsageInfo = UsageInfo()
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    provider: str = ""
    model: str = ""
    iterations: int = 0


class LeadEvent(BaseModel):
    id: str
    type: str
    created_at: str
    fields: dict


class LeadsResponse(BaseModel):
    count: int
    events: list[LeadEvent]
