"""Anthropic backend (tool use + prompt caching).

The translation helpers (`to_anthropic_*`, `parse_response`) are module-level
pure functions so they can be unit-tested with no API key and no network. The
`anthropic` SDK is imported lazily inside the provider class, so importing this
module never requires the package to be installed.
"""
from __future__ import annotations

from typing import Any

from .base import LLMMessage, LLMResponse, ToolCall, ToolSpec, Usage


def to_anthropic_tools(tools: list[ToolSpec] | None) -> list[dict]:
    if not tools:
        return []
    return [
        {"name": t.name, "description": t.description, "input_schema": t.input_schema}
        for t in tools
    ]


def to_anthropic_messages(messages: list[LLMMessage]) -> list[dict]:
    """Translate normalized turns into Anthropic's message format.

    - user text -> {"role": "user", "content": "..."}
    - assistant -> text block(s) + tool_use block(s)
    - tool results -> a user turn of tool_result blocks (Anthropic convention)
    """
    out: list[dict] = []
    for msg in messages:
        if msg.role == "tool":
            out.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": tr.tool_call_id,
                            "content": tr.content,
                            **({"is_error": True} if tr.is_error else {}),
                        }
                        for tr in msg.tool_results
                    ],
                }
            )
        elif msg.role == "assistant":
            blocks: list[dict] = []
            if msg.content:
                blocks.append({"type": "text", "text": msg.content})
            for tc in msg.tool_calls:
                blocks.append(
                    {"type": "tool_use", "id": tc.id, "name": tc.name, "input": tc.arguments}
                )
            out.append({"role": "assistant", "content": blocks})
        else:  # user
            out.append({"role": "user", "content": msg.content})
    return out


def build_system_blocks(system: str) -> list[dict]:
    """Single cacheable system block — the stable prefix shared across requests.

    Per-query retrieved context lives in the user turn, not here, so this prefix
    (plus the tool definitions, which render before it) stays byte-identical and
    is eligible for prompt caching.
    """
    return [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]


def parse_response(message: Any) -> LLMResponse:
    """Normalize an Anthropic Message into an LLMResponse.

    Reads via attribute access so a lightweight stand-in works in tests.
    """
    text_parts: list[str] = []
    tool_calls: list[ToolCall] = []
    for block in message.content:
        btype = getattr(block, "type", None)
        if btype == "text":
            text_parts.append(block.text)
        elif btype == "tool_use":
            tool_calls.append(
                ToolCall(id=block.id, name=block.name, arguments=dict(block.input))
            )
    usage = getattr(message, "usage", None)
    return LLMResponse(
        text="".join(text_parts).strip(),
        tool_calls=tool_calls,
        usage=Usage(
            input_tokens=getattr(usage, "input_tokens", 0) or 0,
            output_tokens=getattr(usage, "output_tokens", 0) or 0,
        ),
        stop_reason=getattr(message, "stop_reason", "end_turn") or "end_turn",
    )


class AnthropicProvider:
    """Calls Claude via the official Anthropic SDK."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-opus-4-8",
        thinking: str = "disabled",
    ) -> None:
        import anthropic  # lazy — only required when this provider is selected

        self.name = "anthropic"
        self.model = model
        self._thinking = thinking
        self._client = anthropic.Anthropic(api_key=api_key)

    def generate(
        self,
        *,
        system: str,
        messages: list[LLMMessage],
        tools: list[ToolSpec] | None = None,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        kwargs: dict = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": build_system_blocks(system),
            "messages": to_anthropic_messages(messages),
        }
        anthropic_tools = to_anthropic_tools(tools)
        if anthropic_tools:
            kwargs["tools"] = anthropic_tools
        if self._thinking == "adaptive":
            kwargs["thinking"] = {"type": "adaptive"}
        message = self._client.messages.create(**kwargs)
        return parse_response(message)
