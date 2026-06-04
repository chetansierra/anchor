"""The AI solutions consultant — the self-referential landing-page agent.

A sibling of `app/agent.py` (the Nimbus support agent), deliberately kept
separate because its contract is different: it never "refuses", it always emits a
*structured* proposal (matched services, a tailored solution sketch, a rough
timeline, proof), and it narrates its work as named stages over SSE.

Flow (one retrieve + one LLM call):
  1. Retrieve top-k chunks from the SERVICES corpus (about the freelancer's work).
  2. Prompt the model with those sources + the visitor's problem and exactly one
     tool, `emit_consult`, whose input schema *is* the proposal. The model calls
     it; we read the structured arguments straight off `ToolCall.arguments`.
  3. Validate into a `ConsultResult`; on any drift, fall back to a safe,
     catalog-derived proposal so the public demo never 500s.

`run_streamed` yields `(event, payload)` tuples for the SSE route; `run` drains
it and returns the typed `ConsultResult`.
"""
from __future__ import annotations

import time
from collections.abc import Iterator

from pydantic import ValidationError

from .config import Settings
from .llm import LLMMessage, LLMProvider, ToolSpec, build_llm_provider
from .llm.pricing import estimate_cost_usd
from .models import ConsultResult
from .retrieval import Retriever
from .services_catalog import (
    CATALOG_BY_ID,
    SERVICE_CATALOG,
    catalog_ids,
    default_consult_payload,
)
from .vectorstore import SearchHit

_CATALOG_LINES = "\n".join(
    f"- {c['id']}: {c['name']} (${c['price_band']['low_usd']}-{c['price_band']['high_usd']})"
    for c in SERVICE_CATALOG
)

CONSULT_SYSTEM_PROMPT = """You are the AI solutions consultant for {name}, a backend engineer who builds production-grade, evaluated AI agents on clients' real data.

A visitor has described an AI problem in their business. Scope it into a concrete, honest mini-proposal by calling the SINGLE tool `emit_consult` exactly once. Ground everything in the SOURCES (which describe {name}'s actual services, approach, and proven results) provided in the user's message — do not invent services, prices, or results the sources don't support.

Pick the 1-3 services from this catalog that genuinely fit (use these exact service_id values; never invent one):
{catalog}

Guidance:
- problem_restatement: restate their problem in one or two plain sentences so they feel understood.
- services: 1-3 matches. For each, give a fit_reason tied to THEIR problem and grounded in the sources, and use the catalog's price band.
- solution: a short, tailored sketch — a summary plus ordered architecture_steps describing how you'd build it (RAG, tool-calling, guardrails, eval, observability as relevant).
- timeline: a few phases with rough durations, drawn from the approach the sources describe.
- proof: cite the measured Nimbus case study (e.g. 92.7% accuracy) as evidence this engine works.

Be concrete and confident but never over-promise; it's fine to note what should stay human-in-the-loop. Call `emit_consult` now — do not reply with prose."""


def _emit_consult_tool() -> ToolSpec:
    return ToolSpec(
        name="emit_consult",
        description=(
            "Return the structured consultation for the visitor's problem: a "
            "restatement, 1-3 matched services, a tailored solution sketch, a rough "
            "timeline, and proof. Call this exactly once with the full proposal."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "problem_restatement": {
                    "type": "string",
                    "description": "One or two sentences restating the visitor's problem in your own words.",
                },
                "services": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 3,
                    "description": "The 1-3 catalog services that fit, best first.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "service_id": {
                                "type": "string",
                                "enum": catalog_ids(),
                                "description": "Which productized service fits (use an exact catalog id).",
                            },
                            "name": {"type": "string"},
                            "fit_reason": {
                                "type": "string",
                                "description": "Why this service fits THEIR problem, grounded in the sources.",
                            },
                            "whats_included": {"type": "array", "items": {"type": "string"}},
                            "price_band": {
                                "type": "object",
                                "properties": {
                                    "label": {"type": "string"},
                                    "low_usd": {"type": "integer"},
                                    "high_usd": {"type": "integer"},
                                },
                                "required": ["low_usd", "high_usd"],
                            },
                            "confidence": {
                                "type": "number",
                                "description": "0..1 confidence that this service fits.",
                            },
                        },
                        "required": ["service_id", "fit_reason"],
                    },
                },
                "solution": {
                    "type": "object",
                    "properties": {
                        "summary": {"type": "string"},
                        "architecture_steps": {"type": "array", "items": {"type": "string"}},
                        "stack_notes": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["summary"],
                },
                "timeline": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "duration": {"type": "string"},
                            "deliverable": {"type": "string"},
                        },
                        "required": ["name", "duration"],
                    },
                },
                "proof": {
                    "type": "object",
                    "properties": {
                        "headline": {"type": "string"},
                        "detail": {"type": "string"},
                        "case_study_url": {"type": "string"},
                    },
                    "required": ["headline"],
                },
            },
            "required": ["problem_restatement", "services", "solution", "proof"],
        },
    )


def _format_sources(hits: list[SearchHit], max_chars: int) -> str:
    lines = ["SOURCES (about the consultant's services):"]
    for i, h in enumerate(hits, 1):
        text = " ".join(h.record.text.split())[:max_chars]
        lines.append(f"[{i}] {h.record.title} ({h.record.source}): {text}")
    return "\n".join(lines)


def _citations(hits: list[SearchHit]) -> list[dict]:
    return [
        {
            "n": i + 1,
            "doc_id": h.record.doc_id,
            "title": h.record.title,
            "source": h.record.source,
            "score": round(h.score, 4),
        }
        for i, h in enumerate(hits)
    ]


def _retrieved_view(hits: list[SearchHit]) -> list[dict]:
    return [
        {
            "rank": i + 1,
            "doc_id": h.record.doc_id,
            "title": h.record.title,
            "source": h.record.source,
            "score": round(h.score, 4),
            "text": h.record.text,
        }
        for i, h in enumerate(hits)
    ]


class ConsultAgent:
    def __init__(
        self,
        retriever: Retriever,
        provider: LLMProvider,
        settings: Settings,
    ) -> None:
        self.retriever = retriever
        self.provider = provider
        self.settings = settings
        self._system = CONSULT_SYSTEM_PROMPT.format(
            name=settings.freelancer_name, catalog=_CATALOG_LINES
        )
        self._tool = _emit_consult_tool()

    @classmethod
    def build(cls, retriever: Retriever, settings: Settings) -> "ConsultAgent":
        return cls(retriever, build_llm_provider(settings), settings)

    def run(self, problem: str) -> ConsultResult:
        """Drain the streamed run and return the final structured result."""
        result: ConsultResult | None = None
        for event, payload in self.run_streamed(problem):
            if event == "result" and isinstance(payload, ConsultResult):
                result = payload
        assert result is not None  # run_streamed always yields exactly one result
        return result

    def run_streamed(self, problem: str) -> Iterator[tuple[str, object]]:
        """Yield staged events, then the final ConsultResult.

        The staging narrates ONE retrieve+generate cycle (not parallel work):
        `understanding` is a quick marker, `matching` wraps the real retrieval,
        `drafting` wraps the real (long-pole) LLM call, and `timeline` is a
        cosmetic marker since the timeline is part of the same structured payload.
        """
        started = time.perf_counter()

        yield ("stage", {"step": "understanding", "label": "Understanding your problem", "status": "start"})

        yield ("stage", {"step": "matching", "label": "Matching services", "status": "start"})
        hits, _ = self.retriever.search(problem, self.settings.consult_top_k)
        yield ("stage", {"step": "matching", "status": "done", "meta": {"docs": len(hits)}})

        yield ("stage", {"step": "drafting", "label": "Drafting an approach", "status": "start"})
        result = self._draft(problem, hits, started)
        yield ("stage", {"step": "drafting", "status": "done"})

        yield ("stage", {"step": "timeline", "label": "Sketching a timeline", "status": "start"})
        yield ("stage", {"step": "timeline", "status": "done"})

        yield ("result", result)

    # --- internals -----------------------------------------------------------
    def _draft(self, problem: str, hits: list[SearchHit], started: float) -> ConsultResult:
        messages = [
            LLMMessage(
                role="user",
                content=(
                    f"{_format_sources(hits, self.settings.source_char_budget)}"
                    f"\n\nVisitor's problem: {problem}"
                ),
            )
        ]
        resp = self.provider.generate(
            system=self._system,
            messages=messages,
            tools=[self._tool],
            max_tokens=self.settings.consult_max_tokens,
        )
        observability = {
            "grounded": bool(hits),
            "citations": _citations(hits),
            "retrieved": _retrieved_view(hits),
            "usage": {
                "input_tokens": resp.usage.input_tokens,
                "output_tokens": resp.usage.output_tokens,
            },
            "cost_usd": estimate_cost_usd(self.provider.model, resp.usage),
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            "provider": self.provider.name,
            "model": self.provider.model,
        }

        args = resp.tool_calls[0].arguments if resp.tool_calls else {}
        args = _sanitize(args)
        try:
            return ConsultResult.model_validate({**args, **observability})
        except ValidationError:
            # A real model returned something that won't validate — never break the
            # demo; serve a safe, catalog-derived proposal instead.
            payload = default_consult_payload(problem)
            return ConsultResult.model_validate({**payload, **observability})


def _sanitize(args: object) -> dict:
    """Coerce a model's emit_consult arguments toward a valid ConsultResult.

    Drops services whose service_id isn't in the catalog and back-fills name /
    whats_included / price_band from the catalog when the model omitted them. If
    nothing valid survives, leaves args as-is so validation trips the fallback.
    """
    if not isinstance(args, dict):
        return {}
    args = dict(args)
    services = args.get("services")
    if isinstance(services, list):
        cleaned = []
        for s in services[:3]:
            if not isinstance(s, dict):
                continue
            cat = CATALOG_BY_ID.get(s.get("service_id"))
            if cat is None:
                continue
            s = dict(s)
            s.setdefault("name", cat["name"])
            if not s.get("whats_included"):
                s["whats_included"] = list(cat["whats_included"])
            if not s.get("price_band"):
                s["price_band"] = dict(cat["price_band"])
            cleaned.append(s)
        if cleaned:
            args["services"] = cleaned
    return args
