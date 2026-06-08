"""FastAPI app: /health, /ingest, /query, /chat, /leads.

Day 1 exposed raw retrieval (/query). Day 2 adds the agent (/chat): grounded,
cited answers plus real tool actions (capture_lead / book_callback) that write to
a mock CRM, readable back via /leads. The retriever is loaded once at startup and
the agent is built lazily on top of it (and rebuilt after /ingest).
"""
from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response, StreamingResponse

from . import __version__
from .admin_leads_page import ADMIN_LEADS_HTML
from .admin_page import ADMIN_HTML
from .agent import Agent, AgentResult
from .config import get_settings
from .consult import ConsultAgent
from .ingest import run_ingest
from .leads import build_lead_store
from .limits import RateLimiter, enforce_demo_limits
from .models import (
    CatalogResponse,
    CatalogService,
    ChatRequest,
    ChatResponse,
    ConsultDecline,
    ConsultLeadRequest,
    ConsultRequest,
    ConsultResult,
    ConversationsResponse,
    HealthResponse,
    IngestResponse,
    KbResponse,
    LeadRow,
    LeadsResponse,
    LeadUpdateRequest,
    OverviewResponse,
    QueryRequest,
    QueryResponse,
    RetrievedChunk,
)
from .retrieval import Retriever
from .services_catalog import SERVICE_CATALOG
from .traces import TraceStore
from .vectorstore import LocalVectorStore

# Module-level state for the single-process demo. Two corpora: the Nimbus support
# index (/chat) and the services index (/consult, the landing-page consultant).
_state: dict = {
    "retriever": None,
    "agent": None,
    "services_retriever": None,
    "consult_agent": None,
}


def _load_retriever_safely(index_path: Path | None = None) -> Retriever | None:
    settings = get_settings()
    target = index_path or settings.index_path
    if not LocalVectorStore.exists(target):
        return None
    try:
        return Retriever.load(settings, index_path=target)
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


def _get_consult_agent() -> ConsultAgent | None:
    """Build (and cache) the consultant agent on the services index. Returns None
    if that index isn't built; raises if the LLM provider can't be built."""
    if _state["consult_agent"] is not None:
        return _state["consult_agent"]
    retriever = _state["services_retriever"]
    if retriever is None:
        return None
    _state["consult_agent"] = ConsultAgent.build(retriever, get_settings())
    return _state["consult_agent"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    _state["retriever"] = _load_retriever_safely()
    _state["services_retriever"] = _load_retriever_safely(settings.services_index_path)
    _state["agent"] = None
    _state["consult_agent"] = None
    try:  # create the leads table if using Postgres; harmless for the JSONL store
        _lead_store.ensure_schema()
    except Exception:
        pass
    yield


app = FastAPI(title="Anchor Support Agent", version=__version__, lifespan=lifespan)

# CORS so the one-script-tag widget works when embedded on another origin.
_origins = [o.strip() for o in get_settings().cors_allow_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins or ["*"],
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["*"],
)

# Per-IP rate limiter for the open demo (shared across requests, single process).
_rate_limiter = RateLimiter(get_settings().rate_limit_per_minute)

# Durable lead store (Postgres when DATABASE_URL is set, else local JSONL).
_lead_store = build_lead_store(get_settings())


def _require_admin(token: str | None) -> None:
    """Gate the leads admin + /leads when an ADMIN_TOKEN is configured (prod).
    Unset -> open (local dev), mirroring the demo-API-key seam."""
    expected = get_settings().admin_token
    if expected and token != expected:
        raise HTTPException(status_code=401, detail="Admin token required.")

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


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def root() -> HTMLResponse:
    """The portfolio site — hero, services, the live demo (this widget), the eval
    case study, and a single email CTA. The front door for visitors and clients."""
    return HTMLResponse((_STATIC / "portfolio.html").read_text(encoding="utf-8"))


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
        # Rebuild the services corpus too (best-effort: it may not exist on a
        # fresh checkout, and the support demo shouldn't fail if it's missing).
        try:
            run_ingest(
                settings,
                kb_path=settings.services_kb_path,
                index_path=settings.services_index_path,
            )
        except FileNotFoundError:
            pass
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    _state["retriever"] = _load_retriever_safely()
    _state["services_retriever"] = _load_retriever_safely(settings.services_index_path)
    _state["agent"] = None  # rebuild against the fresh index on next use
    _state["consult_agent"] = None
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
def leads(
    limit: int = 100,
    source: str | None = None,
    status: str | None = None,
    country: str | None = None,
    talk_to: bool | None = None,
    q: str | None = None,
    x_admin_token: str | None = Header(default=None),
    token: str | None = None,
) -> LeadsResponse:
    """Recent leads (newest first), filterable. Admin-gated when ADMIN_TOKEN is set
    (real prospect PII). The admin page passes the token via header or ?token=."""
    _require_admin(x_admin_token or token)
    rows = _lead_store.recent(
        limit, source=source, status=status, country=country, talk_to=talk_to, q=q
    )
    return LeadsResponse(count=len(rows), leads=rows)


@app.get("/admin/leads", response_class=HTMLResponse, include_in_schema=False)
def admin_leads(token: str | None = None) -> HTMLResponse:
    """The leads dashboard — a self-contained page that reads /leads and lets you
    set talk_to / country / note / status. Gated by ?token= when configured."""
    _require_admin(token)
    return HTMLResponse(ADMIN_LEADS_HTML)


@app.patch("/admin/leads/{lead_id}", response_model=LeadRow)
def admin_lead_update(
    lead_id: str,
    req: LeadUpdateRequest,
    x_admin_token: str | None = Header(default=None),
    token: str | None = None,
) -> LeadRow:
    _require_admin(x_admin_token or token)
    updated = _lead_store.update(lead_id, req.model_dump(exclude_unset=True))
    if updated is None:
        raise HTTPException(status_code=404, detail=f"No lead {lead_id!r}.")
    return LeadRow(**updated)


# --- Consult: the AI solutions consultant (v2 hero) -------------------------


def _sse(event: str, data: dict) -> str:
    """One Server-Sent-Events frame: an event name + a JSON data line."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.post("/consult/stream")
def consult_stream(
    req: ConsultRequest,
    request: Request,
    x_api_key: str | None = Header(default=None),
) -> StreamingResponse:
    """Stream the consultant's reasoning as named stages, then the structured
    result, over SSE. The visitor watches it think, then gets the cards.

    Guardrails are enforced pre-flight (real HTTP error before the stream opens);
    failures mid-stream are surfaced as an `error` frame so the client always
    gets a clean terminator."""
    if _state["services_retriever"] is None:
        raise HTTPException(
            status_code=409,
            detail="No services index loaded. POST /ingest first to build it.",
        )
    settings = get_settings()
    store = TraceStore(settings.traces_path)
    enforce_demo_limits(
        ip=request.client.host if request.client else "unknown",
        api_key=x_api_key,
        settings=settings,
        limiter=_rate_limiter,
        store=store,
    )
    try:
        agent = _get_consult_agent()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"LLM provider unavailable: {exc}") from exc
    assert agent is not None

    def gen():
        result: ConsultResult | None = None
        decline: ConsultDecline | None = None
        try:
            for event, payload in agent.run_streamed(req.problem):
                if event == "result" and isinstance(payload, ConsultResult):
                    result = payload
                    yield _sse("result", payload.model_dump())
                elif event == "declined" and isinstance(payload, ConsultDecline):
                    decline = payload
                    yield _sse("declined", payload.model_dump())
                elif isinstance(payload, dict):
                    yield _sse(event, payload)
            try:  # best-effort trace; never break the stream on a write error
                if result is not None:
                    store.record_consult(req.problem, result)
                elif decline is not None:
                    store.record_consult_decline(req.problem, decline)
            except Exception:
                pass
        except Exception as exc:
            yield _sse("error", {"detail": str(exc), "code": 500})
        yield _sse("done", {})

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # disable nginx/proxy buffering of the stream
        },
    )


@app.post("/consult/lead")
def consult_lead(
    req: ConsultLeadRequest,
    request: Request,
    x_api_key: str | None = Header(default=None),
) -> dict:
    """Capture a lead from the consultant CTA into the mock CRM. Free action, so
    it's gated by the API key + rate limit but NOT the daily cost ceiling — we
    never want to drop a lead because the LLM budget is spent."""
    settings = get_settings()
    if settings.demo_api_key and x_api_key != settings.demo_api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")
    ip = request.client.host if request.client else "unknown"
    if not _rate_limiter.allow(ip):
        raise HTTPException(
            status_code=429,
            detail="You're sending requests a bit fast — please wait a moment and try again.",
            headers={"Retry-After": "30"},
        )
    lead = _lead_store.add(
        "consult",
        {
            "email": req.email,
            "contact": req.contact,
            "problem": req.problem,
            "services": req.services,
        },
    )
    return {"id": lead["id"], "status": "captured"}


@app.get("/consult/catalog", response_model=CatalogResponse)
def consult_catalog() -> CatalogResponse:
    """The productized service catalog the consultant maps problems onto — lets
    the front-end render fallback cards / suggestion chips without a model call."""
    services = [
        CatalogService(
            id=c["id"],
            name=c["name"],
            price_band=c["price_band"],
            whats_included=c["whats_included"],
        )
        for c in SERVICE_CATALOG
    ]
    return CatalogResponse(count=len(services), services=services)


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


@app.get("/kb", response_model=KbResponse)
def kb() -> KbResponse:
    """The documents the agent can answer from — makes 'answers from your data'
    tangible (the portfolio lists these so visitors know what to ask)."""
    settings = get_settings()
    retriever = _state["retriever"]
    docs = retriever.store.documents() if retriever is not None else []
    return KbResponse(business=settings.business_name, count=len(docs), documents=docs)


@app.get("/demo", response_class=HTMLResponse, include_in_schema=False)
def demo_page() -> HTMLResponse:
    """A throwaway page that embeds the widget — the live one-script-tag check."""
    return HTMLResponse((_STATIC / "embed-test.html").read_text(encoding="utf-8"))
