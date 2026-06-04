"""Normalized types shared by every LLM provider.

These are deliberately provider-neutral. Each provider adapter converts this
shape to and from its native SDK format, so the agent loop never sees a
provider-specific object.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class ToolSpec:
    """A tool the model may call (provider-neutral JSON-schema form)."""

    name: str
    description: str
    input_schema: dict


@dataclass
class ToolCall:
    """A model's request to invoke a tool."""

    id: str
    name: str
    arguments: dict


@dataclass
class ToolResult:
    """The outcome of executing a ToolCall, fed back to the model."""

    tool_call_id: str
    content: str
    is_error: bool = False


@dataclass
class LLMMessage:
    """One conversation turn.

    role="user"      -> content is the user's text
    role="assistant" -> content is text and/or tool_calls
    role="tool"      -> tool_results carries one entry per prior tool_call
    """

    role: str
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0

    def __add__(self, other: "Usage") -> "Usage":
        return Usage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
        )


@dataclass
class LLMResponse:
    """A single model turn, normalized across providers."""

    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    stop_reason: str = "end_turn"  # "end_turn" | "tool_use" | "max_tokens" | ...


@runtime_checkable
class LLMProvider(Protocol):
    """The single seam every backend implements."""

    name: str
    model: str

    def generate(
        self,
        *,
        system: str,
        messages: list[LLMMessage],
        tools: list[ToolSpec] | None = None,
        max_tokens: int = 1024,
    ) -> LLMResponse: ...
