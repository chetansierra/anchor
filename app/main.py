"""FastAPI app: /health, /ingest, /query, /chat, /leads.

Day 1 exposed raw retrieval (/query). Day 2 adds the agent (/chat): grounded,
cited answers plus real tool actions (capture_lead / book_callback) that write to
a mock CRM, readable back via /leads. The retriever is loaded once at startup and
the agent is built lazily on top of it (and rebuilt after /ingest).
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response

from . import __version__
from .admin_page import ADMIN_HTML
from .agent import Agent, AgentResult
from .config import get_settings
from .ingest import run_ingest
from .limits import RateLimiter, enforce_demo_limits
from .models import (
    ChatRequest,
    ChatResponse,
    ConversationsResponse,
    HealthResponse,
    IngestResponse,
    LeadsResponse,
    OverviewResponse,
    QueryRequest,
    QueryResponse,
    RetrievedChunk,
)
from .retrieval import Retriever
from .tools import MockCRM
from .traces import TraceStore
from .vectorstore import LocalVectorStore

# Module-level state for the single-process demo.
_state: dict = {"retriever": None, "agent": None}


def _load_retriever_safely() -> Retriever | None:
    settings = get_settings()
    if not LocalVectorStore.exists(settings.index_path):
        return None
    try:
        return Retriever.load(settings)
    except Exception:
        return None


def _get_agent() -> Agent | None:
    """Build (and cache) the agent on top of the loaded retriever. Returns None
    if there's no index; raises if the configured LLM provider can't be built."""
    if _state["agent"] is not None:
        return _state["agent"]
    retriever = _state["retriever"]
    if retriever is None:
        return None
    _state["agent"] = Agent.build(retriever, get_settings())
    return _state["agent"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    _state["retriever"] = _load_retriever_safely()
    _state["agent"] = None
    yield


app = FastAPI(title="Anchor Support Agent", version=__version__, lifespan=lifespan)

# CORS so the one-script-tag widget works when embedded on another origin.
_origins = [o.strip() for o in get_settings().cors_allow_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins or ["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Per-IP rate limiter for the open demo (shared across requests, single process).
_rate_limiter = RateLimiter(get_settings().rate_limit_per_minute)

_STATIC = Path(__file__).resolve().parent / "static"
# Suggested prompt chips the widget shows on open (grounded in the seeded KB).
SUGGESTED_PROMPTS = [
    "How do I reset my password?",
    "Do you support SAML SSO?",
    "What are your API rate limits?",
    "Can I get a refund after I cancel?",
]


def _to_chat_response(result: AgentResult) -> ChatResponse:
    return ChatResponse(
        answer=result.answer,
        grounded=result.grounded,
        escalated=result.escalated,
        citations=result.citations,
        tool_calls=[vars(t) for t in result.tool_calls],
        retrieved=result.retrieved,
        usage={"input_tokens": result.usage.input_tokens, "output_tokens": result.usage.output_tokens},
        cost_usd=result.cost_usd,
        latency_ms=result.latency_ms,
        provider=result.provider,
        model=result.model,
        iterations=result.iterations,
    )


@app.get("/", include_in_schema=False)
def root() -> dict:
    return {
        "service": "Anchor Support Agent",
        "version": __version__,
        "endpoints": ["/health", "/ingest", "/query", "/chat", "/leads", "/docs"],
    }


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    retriever = _state["retriever"]
    if retriever is None:
        return HealthResponse(status="ok", business=settings.business_name)

    provider = model = None
    try:  # report the resolved provider without failing health on a bad key
        agent = _get_agent()
        if agent is not None:
            provider, model = agent.provider.name, agent.provider.model
    except Exception:
        pass

    return HealthResponse(
        status="ok",
        business=settings.business_name,
        embedder=retriever.embedder.name,
        indexed_chunks=retriever.store.count,
        indexed_documents=retriever.store.n_documents,
        provider=provider,
        model=model,
    )


@app.post("/ingest", response_model=IngestResponse)
def ingest() -> IngestResponse:
    settings = get_settings()
    try:
        stats = run_ingest(settings)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    _state["retriever"] = _load_retriever_safely()
    _state["agent"] = None  # rebuild against the fresh index on next use
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


@app.post("/chat", response_model=ChatResponse)
def chat(
    req: ChatRequest,
    request: Request,
    x_api_key: str | None = Header(default=None),
) -> ChatResponse:
    if _state["retriever"] is None:
        raise HTTPException(
            status_code=409,
            detail="No index loaded. POST /ingest first to build the KB index.",
        )
    settings = get_settings()
    store = TraceStore(settings.traces_path)
    # Public-demo guardrails: API-key seam, per-IP rate limit, daily cost ceiling.
    enforce_demo_limits(
        ip=request.client.host if request.client else "unknown",
        api_key=x_api_key,
        settings=settings,
        limiter=_rate_limiter,
        store=store,
    )
    try:
        agent = _get_agent()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"LLM provider unavailable: {exc}") from exc
    assert agent is not None
    result = agent.run(req.message, req.top_k)
    try:  # best-effort: a trace write must never break a live answer
        store.record(req.message, result)
    except Exception:
        pass
    return _to_chat_response(result)


@app.get("/leads", response_model=LeadsResponse)
def leads(limit: int = 20) -> LeadsResponse:
    settings = get_settings()
    events = MockCRM(settings.crm_path).recent(limit)
    return LeadsResponse(count=len(events), events=events)


# --- Observability / admin (Day 4) ------------------------------------------


@app.get("/admin", response_class=HTMLResponse, include_in_schema=False)
def admin_dashboard() -> HTMLResponse:
    return HTMLResponse(ADMIN_HTML)


@app.get("/admin/overview", response_model=OverviewResponse)
def admin_overview() -> OverviewResponse:
    ov = TraceStore(get_settings().traces_path).overview()
    return OverviewResponse(**vars(ov))


@app.get("/admin/conversations", response_model=ConversationsResponse)
def admin_conversations(limit: int = 50, outcome: str | None = None) -> ConversationsResponse:
    """Recent conversation summaries. Pass ?outcome=escalated|error to list the
    runs worth reviewing; each row carries its own cost-per-conversation."""
    rows = TraceStore(get_settings().traces_path).recent(limit, outcome)
    return ConversationsResponse(count=len(rows), conversations=rows)


@app.get("/admin/conversations/{trace_id}")
def admin_conversation(trace_id: str) -> dict:
    """The full trace for one conversation — retrieved chunks + scores, tool
    calls, tokens, $ cost, latency. (Acceptance: open any past run, see it all.)"""
    trace = TraceStore(get_settings().traces_path).get(trace_id)
    if trace is None:
        raise HTTPException(status_code=404, detail=f"No trace {trace_id!r}.")
    return trace


# --- Embeddable widget (Day 5) ----------------------------------------------


@app.get("/widget.js", include_in_schema=False)
def widget_js() -> Response:
    """The one-script-tag widget. Served with a JS content-type and a short cache."""
    js = (_STATIC / "widget.js").read_text(encoding="utf-8")
    return Response(
        content=js,
        media_type="application/javascript",
        headers={"Cache-Control": "public, max-age=300"},
    )


@app.get("/widget/config")
def widget_config() -> dict:
    """Lets the widget self-configure: business name + suggested prompt chips."""
    s = get_settings()
    return {"business": s.business_name, "suggested": SUGGESTED_PROMPTS}


@app.get("/demo", response_class=HTMLResponse, include_in_schema=False)
def demo_page() -> HTMLResponse:
    """A throwaway page that embeds the widget — the live one-script-tag check."""
    return HTMLResponse((_STATIC / "embed-test.html").read_text(encoding="utf-8"))
