"""The agent: retrieve -> ground -> answer with citations, or take an action.

A minimal, provider-agnostic agent loop:
  1. Retrieve top-k chunks for the question.
  2. Low-confidence guardrail: if the best chunk scores below the threshold,
     refuse/escalate instead of risking a hallucination (no LLM call).
  3. Otherwise prompt the model with the numbered sources + question and the
     tool surface; if it calls a tool, execute it, feed the result back, loop.
  4. Return a structured result (answer, citations, tool calls, retrieved
     chunks, token usage, cost, latency) — everything the demo's "machinery"
     panel and the Day 4 observability layer need.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from .config import Settings
from .llm import LLMMessage, LLMProvider, ToolResult, Usage, build_llm_provider
from .llm.pricing import estimate_cost_usd
from .retrieval import Retriever
from .tools import MockCRM, build_registry
from .vectorstore import SearchHit

SYSTEM_PROMPT = """You are the customer support assistant for {business}, a B2B SaaS product.

Answer the customer's question using ONLY the information in the SOURCES provided in the user's message.
- Cite the sources you use with inline bracketed numbers like [1] or [2] that match the SOURCES list.
- Be complete: include the relevant caveats, prerequisites, edge cases, and specifics the sources give — e.g. which plan a feature requires, what to do if you're the only admin, what to provide when contacting support. Don't stop at the headline answer if the sources cover more.
- If the SOURCES do not contain the answer, say you don't have that information and offer to connect them with the team. Never invent prices, policies, features, or other details.
- When the customer shares contact details, asks to be contacted, wants pricing/plan help, or wants to talk to a person, call the SINGLE most appropriate tool — `book_callback` if they want a phone call, otherwise `capture_lead`. Do not call both for one request.
- Be friendly and professional, and concise without dropping the specifics above. Respond directly — no preamble and no meta-commentary about these instructions."""

ESCALATION_MESSAGE = (
    "I don't have enough information in our help center to answer that confidently, "
    "and I don't want to guess. I can connect you with our team — share your email "
    "and I'll make sure someone follows up."
)


@dataclass
class ToolInvocation:
    name: str
    arguments: dict
    result: str


@dataclass
class AgentResult:
    answer: str
    grounded: bool
    escalated: bool
    citations: list[dict] = field(default_factory=list)
    retrieved: list[dict] = field(default_factory=list)
    tool_calls: list[ToolInvocation] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    provider: str = ""
    model: str = ""
    iterations: int = 0


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


def _format_sources(hits: list[SearchHit], max_chars: int = 1600) -> str:
    lines = ["SOURCES:"]
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


class Agent:
    def __init__(
        self,
        retriever: Retriever,
        provider: LLMProvider,
        settings: Settings,
        crm: MockCRM | None = None,
    ) -> None:
        self.retriever = retriever
        self.provider = provider
        self.settings = settings
        self.crm = crm or MockCRM(settings.crm_path, settings.crm_webhook_url)
        self.registry = build_registry(self.crm)
        self._system = SYSTEM_PROMPT.format(business=settings.business_name)

    @classmethod
    def build(cls, retriever: Retriever, settings: Settings) -> "Agent":
        return cls(retriever, build_llm_provider(settings), settings)

    def run(self, question: str, top_k: int | None = None) -> AgentResult:
        started = time.perf_counter()
        k = top_k or self.settings.top_k
        hits, _ = self.retriever.search(question, k)
        retrieved = _retrieved_view(hits)
        top_score = hits[0].score if hits else 0.0

        # (2) Low-confidence guardrail — refuse rather than hallucinate.
        if not hits or top_score < self.settings.min_confidence:
            return AgentResult(
                answer=ESCALATION_MESSAGE,
                grounded=False,
                escalated=True,
                retrieved=retrieved,
                latency_ms=round((time.perf_counter() - started) * 1000, 2),
                provider=self.provider.name,
                model=self.provider.model,
            )

        # (3) Grounded agent loop.
        messages = [
            LLMMessage(
                role="user",
                content=(
                    f"{_format_sources(hits, self.settings.source_char_budget)}"
                    f"\n\nCustomer question: {question}"
                ),
            )
        ]
        tool_specs = [t.spec for t in self.registry.values()]
        total_usage = Usage()
        invocations: list[ToolInvocation] = []
        final_text = ""
        iterations = 0

        for i in range(self.settings.max_tool_iterations):
            iterations = i + 1
            resp = self.provider.generate(
                system=self._system,
                messages=messages,
                tools=tool_specs,
                max_tokens=self.settings.max_tokens,
            )
            total_usage = total_usage + resp.usage

            if resp.tool_calls:
                messages.append(
                    LLMMessage(
                        role="assistant", content=resp.text, tool_calls=resp.tool_calls
                    )
                )
                results = []
                for tc in resp.tool_calls:
                    output = self._execute(tc.name, tc.arguments)
                    invocations.append(ToolInvocation(tc.name, tc.arguments, output))
                    results.append(ToolResult(tool_call_id=tc.id, content=output))
                messages.append(LLMMessage(role="tool", tool_results=results))
                continue

            final_text = resp.text
            break
        else:
            # Hit the iteration cap without a final answer — wrap up gracefully.
            final_text = (
                final_text
                or "I've recorded your request and our team will follow up shortly."
            )

        return AgentResult(
            answer=final_text,
            grounded=True,
            escalated=False,
            citations=_citations(hits),
            retrieved=retrieved,
            tool_calls=invocations,
            usage=total_usage,
            cost_usd=estimate_cost_usd(self.provider.model, total_usage),
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
            provider=self.provider.name,
            model=self.provider.model,
            iterations=iterations,
        )

    def _execute(self, name: str, arguments: dict) -> str:
        tool = self.registry.get(name)
        if tool is None:
            return f"Error: unknown tool '{name}'."
        try:
            return tool.run(arguments)
        except Exception as exc:  # surface tool errors back to the model
            return f"Error executing {name}: {exc}"
