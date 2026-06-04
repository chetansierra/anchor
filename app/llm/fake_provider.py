"""Deterministic, keyless provider for tests and offline local runs.

Two modes:
  - **Scripted** — `FakeProvider(script=[LLMResponse, ...])` returns those
    responses in order. Used by tests to drive exact agent behavior.
  - **Heuristic** — with no script, it inspects the conversation and produces a
    plausible response (answer from context, or a tool call when the user asks
    to be contacted). Lets the demo run end-to-end with no API key.

`always_tool` makes it return the same tool call forever — used to test that the
agent loop terminates at `max_tool_iterations`.
"""
from __future__ import annotations

import re

from ..services_catalog import default_consult_payload
from .base import LLMMessage, LLMResponse, ToolCall, ToolSpec, Usage

_LEAD_INTENT = (
    "call me",
    "callback",
    "call back",
    "contact me",
    "talk to sales",
    "reach out",
    "email me",
    "get in touch",
    "book a call",
    "schedule a call",
)


def _latest_question(messages: list[LLMMessage]) -> str:
    for msg in reversed(messages):
        if msg.role == "user":
            return msg.content
    return ""


def _first_source_snippet(user_content: str) -> str:
    """Pull the text of source [1] out of the agent's formatted context block."""
    match = re.search(r"\[1\][^\n]*?:\s*(.+)", user_content)
    if match:
        return match.group(1).strip()[:160]
    return "see the linked source"


class FakeProvider:
    name = "fake"
    model = "fake-1"

    def __init__(
        self,
        script: list[LLMResponse] | None = None,
        always_tool: ToolCall | None = None,
    ) -> None:
        self._script = list(script) if script else None
        self._always_tool = always_tool
        self.calls: list[dict] = []

    def generate(
        self,
        *,
        system: str,
        messages: list[LLMMessage],
        tools: list[ToolSpec] | None = None,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        self.calls.append({"system": system, "messages": messages, "tools": tools})

        if self._always_tool is not None:
            return LLMResponse(
                tool_calls=[self._always_tool], stop_reason="tool_use", usage=Usage(10, 5)
            )
        if self._script:
            return self._script.pop(0)
        return self._heuristic(messages, tools)

    def _heuristic(
        self, messages: list[LLMMessage], tools: list[ToolSpec] | None
    ) -> LLMResponse:
        # Consultant agent: when the `emit_consult` tool is on the surface, return
        # a deterministic, schema-valid structured proposal so the landing-page
        # consultant + its SSE stream run fully keyless (CI + offline demo).
        if tools and any(t.name == "emit_consult" for t in tools):
            problem = _latest_question(messages).split("Visitor's problem:")[-1].strip()
            return LLMResponse(
                tool_calls=[
                    ToolCall(
                        id="fake_consult_1",
                        name="emit_consult",
                        arguments=default_consult_payload(problem),
                    )
                ],
                stop_reason="tool_use",
                usage=Usage(220, 160),
            )

        last = messages[-1] if messages else None
        if last is not None and last.role == "tool":
            result = last.tool_results[0].content if last.tool_results else ""
            return LLMResponse(
                text=f"All set — {result} Is there anything else I can help with? [1]",
                stop_reason="end_turn",
                usage=Usage(20, 12),
            )

        question = _latest_question(messages)
        # Use the actual question only — the user content also carries the
        # retrieved SOURCES, whose text would false-trigger intent detection.
        clean_q = question.split("Customer question:")[-1].strip()
        if tools and any(word in clean_q.lower() for word in _LEAD_INTENT):
            tool = next(
                (t for t in tools if t.name in ("book_callback", "capture_lead")), tools[0]
            )
            return LLMResponse(
                tool_calls=[
                    ToolCall(
                        id="fake_call_1",
                        name=tool.name,
                        arguments={
                            "name": "Demo User",
                            "email": "demo@example.com",
                            "summary": clean_q[:160],
                        },
                    )
                ],
                stop_reason="tool_use",
                usage=Usage(30, 8),
            )

        snippet = _first_source_snippet(question)
        return LLMResponse(
            text=f"Based on our documentation: {snippet} [1]",
            stop_reason="end_turn",
            usage=Usage(40, 15),
        )
