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
from .models import ConsultDecline, ConsultResult
from .retrieval import Retriever
from .screening import DECLINE_MESSAGE, is_blocked
from .services_catalog import (
    SERVICE_CATALOG,
    catalog_ids,
    default_consult_payload,
    enrich_payload,
)
from .vectorstore import SearchHit

_CATALOG_LINES = "\n".join(
    f"- {c['id']}: {c['name']} (${c['price_band']['low_usd']}-{c['price_band']['high_usd']})"
    for c in SERVICE_CATALOG
)

CONSULT_SYSTEM_PROMPT = """You are the AI solutions consultant for {name}, a backend engineer who builds production-grade, evaluated AI agents on clients' real data.

A visitor has described an AI problem. Scope it by calling the SINGLE tool `emit_consult` exactly once. Ground everything in the SOURCES (which describe {name}'s actual services and approach) in the user's message — don't invent capabilities the sources don't support.

SCOPE & COMPLIANCE: Only help with legitimate, lawful AI needs for a business or organization. If the request is NOT a genuine business/organizational use case — e.g. personal academic dishonesty (cheating, homework, exams), or anything harmful, illegal, deceptive, or clearly off-topic — set `in_scope` to false, give a one-line `decline_reason`, and do NOT propose any services. Otherwise set `in_scope` to true and fill the proposal below. (Note: legitimate business requests that merely mention schools, exams, or similar — e.g. an edtech product, or grading tools a company sells — ARE in scope.)

Choose the 1-3 services that genuinely fit, using these exact service_id values (never invent one):
{catalog}

When `in_scope` is true, provide:
- problem_restatement: one or two plain sentences showing you understood them.
- services: 1-3 matches, each with its service_id and a fit_reason tied to THEIR problem and grounded in the sources. (Pricing and what's-included are filled in automatically — don't restate them.)
- solution: a one-line summary, plus `outcomes` — 3-5 crisp bullet fragments (NOT full sentences) describing what the client GETS: the end product for their business and customers. Describe the result, not the technology, stack, or infrastructure.

Be concrete and honest; it's fine to note what should stay human-in-the-loop. Call `emit_consult` now — no prose reply."""


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
                "in_scope": {
                    "type": "boolean",
                    "description": "true if this is a legitimate business/organizational AI request; false for harmful, unlawful, academic-dishonesty, deceptive, or clearly off-topic requests.",
                },
                "decline_reason": {
                    "type": "string",
                    "description": "If in_scope is false, a short, polite one-line reason. Leave empty when in_scope is true.",
                },
                "problem_restatement": {
                    "type": "string",
                    "description": "One or two sentences restating the visitor's problem in your own words.",
                },
                "services": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 3,
                    "description": "The 1-3 catalog services that fit, best first. Pricing and what's-included are filled in automatically — provide only service_id + fit_reason.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "service_id": {
                                "type": "string",
                                "enum": catalog_ids(),
                                "description": "Which productized service fits (use an exact catalog id).",
                            },
                            "fit_reason": {
                                "type": "string",
                                "description": "Why this service fits THEIR problem, grounded in the sources.",
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
                        "summary": {"type": "string", "description": "One short line framing the solution."},
                        "outcomes": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "3-5 crisp bullet fragments (not full sentences) describing what the client gets — the end product/result, not the tech or infrastructure.",
                        },
                    },
                    "required": ["summary"],
                },
            },
            "required": ["in_scope", "problem_restatement", "services", "solution"],
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

    def run(self, problem: str) -> ConsultResult | ConsultDecline:
        """Drain the streamed run and return the final outcome (proposal or decline)."""
        out: ConsultResult | ConsultDecline | None = None
        for event, payload in self.run_streamed(problem):
            if event == "result" and isinstance(payload, ConsultResult):
                out = payload
            elif event == "declined" and isinstance(payload, ConsultDecline):
                out = payload
        assert out is not None  # always yields exactly one result/decline
        return out

    def run_streamed(self, problem: str) -> Iterator[tuple[str, object]]:
        """Yield staged events, then the final ConsultResult.

        The staging narrates ONE retrieve+generate cycle (not parallel work):
        `understanding` is a quick marker, `matching` wraps the real retrieval,
        `drafting` wraps the real (long-pole) LLM call, and `timeline` is a
        cosmetic marker since the timeline is part of the same structured payload.
        """
        started = time.perf_counter()

        # Compliance pre-screen — decline obvious abuse before spending a model call.
        if is_blocked(problem):
            yield ("declined", ConsultDecline(message=DECLINE_MESSAGE, reason="pre-screen"))
            return

        yield ("stage", {"step": "understanding", "label": "Understanding your problem", "status": "start"})

        yield ("stage", {"step": "matching", "label": "Matching services", "status": "start"})
        hits, _ = self.retriever.search(problem, self.settings.consult_top_k)
        yield ("stage", {"step": "matching", "status": "done", "meta": {"docs": len(hits)}})

        yield ("stage", {"step": "drafting", "label": "Drafting an approach", "status": "start"})
        outcome = self._draft(problem, hits, started)
        yield ("stage", {"step": "drafting", "status": "done"})

        # The model can also decline (in_scope=false) for cases the pre-screen missed.
        if isinstance(outcome, ConsultDecline):
            yield ("declined", outcome)
            return

        yield ("stage", {"step": "timeline", "label": "Sketching a timeline", "status": "start"})
        yield ("stage", {"step": "timeline", "status": "done"})

        yield ("result", outcome)

    # --- internals -----------------------------------------------------------
    def _draft(
        self, problem: str, hits: list[SearchHit], started: float
    ) -> ConsultResult | ConsultDecline:
        messages = [
            LLMMessage(
                role="user",
                content=(
                    f"{_format_sources(hits, self.settings.consult_source_char_budget)}"
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

        # Model-side compliance gate: decline anything it judged out of scope.
        if isinstance(args, dict) and args.get("in_scope") is False:
            return ConsultDecline(
                message=DECLINE_MESSAGE,
                reason=str(args.get("decline_reason") or "model")[:200],
                usage=observability["usage"],
                cost_usd=observability["cost_usd"],
                latency_ms=observability["latency_ms"],
                provider=observability["provider"],
                model=observability["model"],
            )

        # The model authors only tailored prose; enrich_payload merges in the
        # deterministic catalog facts + timeline (script, not tokens).
        enriched = enrich_payload(args, problem)
        try:
            return ConsultResult.model_validate({**enriched, **observability})
        except ValidationError:
            # A real model returned something that won't validate (e.g. no valid
            # service) — never break the demo; serve a safe catalog-derived proposal.
            enriched = enrich_payload(default_consult_payload(problem), problem)
            return ConsultResult.model_validate({**enriched, **observability})
