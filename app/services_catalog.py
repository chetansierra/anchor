"""The productized service catalog + a deterministic consult-payload builder.

This module is intentionally dependency-free (stdlib only). Both the consultant
agent (`app/consult.py`, for its safe fallback + system prompt) and the keyless
`FakeProvider` (`app/llm/fake_provider.py`, for its offline heuristic) import from
here, so the catalog and the default proposal have a single source of truth —
without creating an import cycle through the `app.llm` package.

The catalog is derived from the gig mapping in MAIN_GOAL.MD.
"""
from __future__ import annotations

# Each entry: the stable id the classifier maps to, a display name, the price
# band (matching MAIN_GOAL's gig table), default "what's included" bullets, and
# keywords used by the offline heuristic to guess a fit from a free-form problem.
SERVICE_CATALOG: list[dict] = [
    {
        "id": "rag_support_agent",
        "name": "Website AI support agent",
        "price_band": {"label": "Fixed scope", "low_usd": 300, "high_usd": 800},
        "whats_included": [
            "Ingest your docs/site into a retrieval index",
            "Grounded RAG answers with citations",
            "Anti-hallucination guardrails (refuse when unsure)",
            "Embeddable one-script-tag widget",
        ],
        "keywords": [
            "doc", "docs", "faq", "help center", "help centre", "knowledge base",
            "chatbot", "support", "answer question", "documentation", "website",
            "customer question", "kb",
        ],
    },
    {
        "id": "lead_capture_agent",
        "name": "AI lead-capture & booking agent",
        "price_band": {"label": "Fixed scope", "low_usd": 400, "high_usd": 1000},
        "whats_included": [
            "Grounded support agent over your docs",
            "Tool-calling webhooks into your CRM/sheet",
            "Capture leads and book callbacks automatically",
            "Visible 'lead captured' confirmation",
        ],
        "keywords": [
            "lead", "leads", "booking", "book a call", "capture", "sales",
            "convert", "conversion", "crm", "sign up", "signup", "demo request",
            "qualify", "contact form",
        ],
    },
    {
        "id": "workflow_automation",
        "name": "\"Automate this workflow\" with AI",
        "price_band": {"label": "Fixed scope", "low_usd": 200, "high_usd": 600},
        "whats_included": [
            "One scoped workflow with clear inputs/outputs",
            "AI wired to your tools with retries + error handling",
            "Human-in-the-loop checkpoint where needed",
            "Logging of every action and its cost",
        ],
        "keywords": [
            "automate", "automation", "workflow", "n8n", "zapier", "make.com",
            "repetitive", "triage", "route", "routing", "extract", "summarize",
            "summarise", "classify", "tagging", "pipeline",
        ],
    },
    {
        "id": "agentic_function",
        "name": "Agentic function (sales / email assistant)",
        "price_band": {"label": "Scoped to the role", "low_usd": 500, "high_usd": 1200},
        "whats_included": [
            "Multi-step agent loop with planning + multiple tools",
            "Integrations with the systems the role touches",
            "Iteration caps and human approval on costly actions",
            "Evaluation on representative scenarios",
        ],
        "keywords": [
            "agent", "agentic", "sales agent", "sales manager", "email manager",
            "email agent", "assistant", "multi-step", "multi step", "autonomous",
            "sdr", "inbox", "manage my email", "research agent",
        ],
    },
    {
        "id": "internal_tooling",
        "name": "AI internal-tooling integration",
        "price_band": {"label": "Fixed scope", "low_usd": 400, "high_usd": 1000},
        "whats_included": [
            "Private, access-controlled index over internal data",
            "Grounded internal assistant with citations",
            "Optional tool-calling into internal APIs",
            "Observability + a cost ceiling",
        ],
        "keywords": [
            "internal", "internal tool", "internal tooling", "dashboard",
            "employee", "staff", "wiki", "runbook", "intranet", "behind login",
            "behind our auth", "team knowledge", "slack history",
        ],
    },
    {
        "id": "reliability_audit",
        "name": "Agent reliability audit",
        "price_band": {"label": "From", "low_usd": 500, "high_usd": 1500},
        "whats_included": [
            "Labeled test set over your domain",
            "Scoring: retrieval, answer correctness, tool-calls",
            "Report with accuracy % + prioritized fixes",
            "Optional: implement top fixes and re-run",
        ],
        "keywords": [
            "audit", "eval", "evaluate", "evaluation", "hallucinate",
            "hallucination", "accuracy", "test our bot", "test my bot",
            "reliability", "existing bot", "existing agent", "is it accurate",
        ],
    },
]

CATALOG_BY_ID: dict[str, dict] = {c["id"]: c for c in SERVICE_CATALOG}


def catalog_ids() -> list[str]:
    return [c["id"] for c in SERVICE_CATALOG]


def pick_services(problem: str, limit: int = 3) -> list[str]:
    """Heuristic classifier: rank catalog services by keyword hits in the problem.

    Deterministic and keyless — backs both the offline FakeProvider proposal and
    the agent's safe fallback. Always returns at least one id.
    """
    text = (problem or "").lower()
    scored: list[tuple[int, int, str]] = []
    for order, c in enumerate(SERVICE_CATALOG):
        hits = sum(1 for kw in c["keywords"] if kw in text)
        if hits:
            # higher hits first; preserve catalog order on ties
            scored.append((-hits, order, c["id"]))
    if not scored:
        return ["rag_support_agent"]
    scored.sort()
    return [sid for _, _, sid in scored[:limit]]


def _restate(problem: str) -> str:
    p = " ".join((problem or "").split()).strip().rstrip(".")
    if not p:
        return "Here's how I'd approach what you described."
    if len(p) > 220:
        p = p[:217] + "..."
    return f"Here's my read on what you need: {p}."


def default_consult_payload(problem: str, service_ids: list[str] | None = None) -> dict:
    """A complete, schema-valid consult payload (the LLM-authored subset).

    Used (1) by FakeProvider as the offline/keyless proposal and (2) by the agent
    as a safe fallback when a real model returns something that won't validate.
    """
    ids = service_ids or pick_services(problem)
    services = []
    for sid in ids[:3]:
        c = CATALOG_BY_ID.get(sid) or CATALOG_BY_ID["rag_support_agent"]
        services.append(
            {
                "service_id": c["id"],
                "name": c["name"],
                "fit_reason": (
                    f"From what you described, {c['name']} is the most direct fit — "
                    "it's a productized scope I can deliver and evaluate."
                ),
                "whats_included": list(c["whats_included"]),
                "price_band": dict(c["price_band"]),
                "confidence": 0.7,
            }
        )

    return {
        "problem_restatement": _restate(problem),
        "services": services,
        "solution": {
            "summary": (
                "I'd build this as a grounded agent over your own data, with the "
                "production pieces — guardrails, an evaluation harness, and cost "
                "observability — wired in from the start so it holds up in production."
            ),
            "architecture_steps": [
                "Ingest your content/data into a retrieval index",
                "A grounded agent answers (and acts) using only your sources, with citations",
                "Anti-hallucination guardrails refuse when the data doesn't cover it",
                "An evaluation harness measures accuracy before launch",
                "Per-run cost/latency tracing plus a hard daily cost ceiling",
            ],
            "stack_notes": [
                "Provider-agnostic LLM (Claude / OpenAI / Gemini)",
                "RAG retrieval over your data",
                "Tool-calling into your systems",
            ],
        },
        "timeline": [
            {"name": "Discovery & scoping", "duration": "1-2 days", "deliverable": "Fixed scope, success criteria, data sources"},
            {"name": "Ingestion & retrieval", "duration": "1-3 days", "deliverable": "Your data indexed; retrieval returns the right sources"},
            {"name": "Agent & actions", "duration": "2-4 days", "deliverable": "Grounded answers with citations + real tool actions"},
            {"name": "Evaluation", "duration": "1-2 days", "deliverable": "Accuracy report with a number and concrete fixes"},
            {"name": "Observability & deploy", "duration": "1-2 days", "deliverable": "Tracing, cost ceiling, and a deployed agent"},
        ],
        "proof": {
            "headline": "92.7% answer accuracy on 41 labeled cases",
            "detail": (
                "The Nimbus support agent on this site: 100% retrieval hit-rate, "
                "8/8 correct refusals on out-of-scope questions, a fraction of a cent "
                "per run — and every run is traced."
            ),
            "case_study_url": "/#proof",
        },
    }
