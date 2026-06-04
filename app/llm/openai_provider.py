"""OpenAI backend (chat completions + function calling).

Pure translation helpers are module-level; the `openai` SDK is lazy-imported in
the provider class. Not exercised by the test suite (needs an API key) — the
shape follows OpenAI's stable chat-completions tool API.
"""
from __future__ import annotations

import json
from typing import Any

from .base import LLMMessage, LLMResponse, ToolCall, ToolSpec, Usage


def to_openai_tools(tools: list[ToolSpec] | None) -> list[dict]:
    if not tools:
        return []
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.input_schema,
            },
        }
        for t in tools
    ]


def to_openai_messages(system: str, messages: list[LLMMessage]) -> list[dict]:
    out: list[dict] = [{"role": "system", "content": system}]
    for msg in messages:
        if msg.role == "tool":
            for tr in msg.tool_results:
                out.append(
                    {"role": "tool", "tool_call_id": tr.tool_call_id, "content": tr.content}
                )
        elif msg.role == "assistant":
            entry: dict = {"role": "assistant", "content": msg.content or None}
            if msg.tool_calls:
                entry["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                    }
                    for tc in msg.tool_calls
                ]
            out.append(entry)
        else:
            out.append({"role": "user", "content": msg.content})
    return out


def parse_openai_response(resp: Any) -> LLMResponse:
    choice = resp.choices[0]
    msg = choice.message
    tool_calls = [
        ToolCall(
            id=tc.id,
            name=tc.function.name,
            arguments=json.loads(tc.function.arguments or "{}"),
        )
        for tc in (getattr(msg, "tool_calls", None) or [])
    ]
    usage = getattr(resp, "usage", None)
    stop = "tool_use" if choice.finish_reason == "tool_calls" else (choice.finish_reason or "end_turn")
    return LLMResponse(
        text=(msg.content or "").strip(),
        tool_calls=tool_calls,
        usage=Usage(
            input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            output_tokens=getattr(usage, "completion_tokens", 0) or 0,
        ),
        stop_reason=stop,
    )


class OpenAIProvider:
    def __init__(self, api_key: str, model: str = "gpt-4o-mini") -> None:
        from openai import OpenAI  # lazy

        self.name = "openai"
        self.model = model
        self._client = OpenAI(api_key=api_key)

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
            "messages": to_openai_messages(system, messages),
        }
        openai_tools = to_openai_tools(tools)
        if openai_tools:
            kwargs["tools"] = openai_tools
        resp = self._client.chat.completions.create(**kwargs)
        return parse_openai_response(resp)
