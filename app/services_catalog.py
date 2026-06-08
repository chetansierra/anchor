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
            "Instant answers from your own docs",
            "Every answer shows its source",
            "Says when it doesn't know — no made-up answers",
            "Live on your site, on brand",
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
            "Answers customers and captures the lead in one chat",
            "Interested visitors land in your CRM automatically",
            "Books callbacks without a human",
            "Every captured lead visible to you",
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
            "A repetitive task runs itself",
            "Handles the messy cases rules can't",
            "You approve anything risky before it acts",
            "A clear log of what it did",
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
            "An AI that handles a whole role, not one task",
            "Works across the tools you already use",
            "Checks with you before anything costly",
            "Proven on real scenarios before it goes live",
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
            "Your team gets answers in plain English",
            "Pulls from internal docs, with sources",
            "Stays private, behind your login",
            "Predictable, capped running cost",
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
            "Know how accurate your bot really is",
            "See exactly where it fails",
            "A prioritized list of fixes",
            "Optional: I fix the top issues and re-test",
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


# --- Deterministic, script-filled parts of a proposal -------------------------
# These are facts/templates, not model judgment, so a script fills them every
# time instead of spending tokens asking the model (and risking drift). The model
# only authors the *tailored* prose (restatement, fit_reason, solution summary +
# steps); enrich_payload() merges these in afterward.

def default_timeline() -> list[dict]:
    return [
        {"name": "Discovery & scoping", "duration": "1-2 days", "deliverable": "Fixed scope, success criteria, data sources"},
        {"name": "Ingestion & retrieval", "duration": "1-3 days", "deliverable": "Your data indexed; retrieval returns the right sources"},
        {"name": "Agent & actions", "duration": "2-4 days", "deliverable": "Grounded answers with citations + real tool actions"},
        {"name": "Evaluation & deploy", "duration": "1-2 days", "deliverable": "Accuracy checked, then traced, cost-capped, and deployed"},
    ]


def default_consult_payload(problem: str, service_ids: list[str] | None = None) -> dict:
    """The **LLM-authored subset** of a proposal (tailored prose only).

    Deterministic facts — service name / price / what's-included, the timeline,
    stack notes — are NOT here; enrich_payload() fills them from the catalog. Used
    (1) by FakeProvider as the keyless/offline proposal and (2) by the agent as a
    safe fallback when a real model returns something that won't validate.
    """
    ids = service_ids or pick_services(problem)
    services = []
    for sid in ids[:3]:
        c = CATALOG_BY_ID.get(sid) or CATALOG_BY_ID["rag_support_agent"]
        services.append(
            {
                "service_id": c["id"],
                "fit_reason": (
                    f"From what you described, {c['name']} is the most direct fit — "
                    "it's a productized scope I can deliver and evaluate."
                ),
                "confidence": 0.7,
            }
        )

    return {
        "in_scope": True,
        "problem_restatement": _restate(problem),
        "services": services,
        "solution": {
            "summary": (
                "A grounded AI agent over your own data — answering and acting for "
                "you, and dependable enough to run in production."
            ),
            "outcomes": [
                "Answers your users from your own content",
                "Every answer backed by a source",
                "Takes the action for you, not just chat",
                "Won't make things up",
                "You can see what it does and what it costs",
            ],
        },
    }


def enrich_payload(args: dict, problem: str) -> dict:
    """Merge the model's (or fallback's) tailored prose with catalog facts.

    - Drops services with an unknown service_id; back-fills name / what's-included
      / price band from the catalog (facts win over anything the model emitted).
    - Adds the script-filled timeline and stack notes.
    Returns a dict ready to validate as a ConsultResult. If no service survives,
    leaves `services` empty so validation trips the caller's fallback.
    """
    out = dict(args) if isinstance(args, dict) else {}
    out.setdefault("problem_restatement", _restate(problem))

    services = []
    for s in (out.get("services") or [])[:3]:
        if not isinstance(s, dict):
            continue
        cat = CATALOG_BY_ID.get(str(s.get("service_id") or ""))
        if cat is None:
            continue
        services.append(
            {
                "service_id": cat["id"],
                "name": cat["name"],
                "fit_reason": s.get("fit_reason") or f"{cat['name']} fits what you described.",
                "whats_included": list(cat["whats_included"]),
                "price_band": dict(cat["price_band"]),
                "confidence": s.get("confidence", 0.7),
            }
        )
    out["services"] = services

    solution = dict(out.get("solution") or {})
    solution.setdefault("summary", "")
    solution.setdefault("outcomes", [])
    out["solution"] = solution

    out["timeline"] = default_timeline()
    return out
