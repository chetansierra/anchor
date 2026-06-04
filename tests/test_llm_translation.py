"""Pure-function tests for the provider translation layer.

No API key, no network, no SDK install required — these validate the trickiest
part of each adapter (normalized turns -> native message/tool shape).
"""
from __future__ import annotations

from app.llm.anthropic_provider import (
    build_system_blocks,
    to_anthropic_messages,
    to_anthropic_tools,
)
from app.llm.base import LLMMessage, ToolCall, ToolResult, ToolSpec
from app.llm.openai_provider import to_openai_messages, to_openai_tools

_TOOLS = [ToolSpec("capture_lead", "Record a lead", {"type": "object", "properties": {}})]
_CONVO = [
    LLMMessage(role="user", content="hi"),
    LLMMessage(
        role="assistant",
        content="one moment",
        tool_calls=[ToolCall("t1", "capture_lead", {"email": "a@b.com"})],
    ),
    LLMMessage(role="tool", tool_results=[ToolResult("t1", "Lead captured")]),
]


def test_anthropic_tools_translation():
    assert to_anthropic_tools(_TOOLS) == [
        {"name": "capture_lead", "description": "Record a lead", "input_schema": {"type": "object", "properties": {}}}
    ]
    assert to_anthropic_tools(None) == []


def test_anthropic_messages_translation():
    out = to_anthropic_messages(_CONVO)
    assert out[0] == {"role": "user", "content": "hi"}
    assert out[1]["role"] == "assistant"
    assert out[1]["content"][0] == {"type": "text", "text": "one moment"}
    assert out[1]["content"][1] == {
        "type": "tool_use",
        "id": "t1",
        "name": "capture_lead",
        "input": {"email": "a@b.com"},
    }
    assert out[2] == {
        "role": "user",
        "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "Lead captured"}],
    }


def test_anthropic_system_block_is_cacheable():
    blocks = build_system_blocks("static instructions")
    assert blocks[0]["text"] == "static instructions"
    assert blocks[0]["cache_control"] == {"type": "ephemeral"}


def test_openai_tools_and_messages_translation():
    tools = to_openai_tools(_TOOLS)
    assert tools[0]["type"] == "function"
    assert tools[0]["function"]["name"] == "capture_lead"

    out = to_openai_messages("system prompt", _CONVO)
    assert out[0] == {"role": "system", "content": "system prompt"}
    assert out[1] == {"role": "user", "content": "hi"}
    assert out[2]["role"] == "assistant"
    assert out[2]["tool_calls"][0]["function"]["name"] == "capture_lead"
    assert out[3] == {"role": "tool", "tool_call_id": "t1", "content": "Lead captured"}
