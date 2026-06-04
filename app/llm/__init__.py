"""Provider-agnostic LLM layer (strategy pattern).

The agent depends only on the `LLMProvider` protocol and the normalized types in
`base`. Concrete backends (Anthropic, OpenAI, Gemini, Fake) translate to/from
their native SDK formats and are selected at runtime by `build_llm_provider`.
"""
from __future__ import annotations

from .base import (
    LLMMessage,
    LLMProvider,
    LLMResponse,
    ToolCall,
    ToolResult,
    ToolSpec,
    Usage,
)
from .factory import build_llm_provider

__all__ = [
    "LLMMessage",
    "LLMProvider",
    "LLMResponse",
    "ToolCall",
    "ToolResult",
    "ToolSpec",
    "Usage",
    "build_llm_provider",
]
