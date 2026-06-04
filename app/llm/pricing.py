"""Rough per-model pricing for cost estimates (USD per 1M tokens).

Best-effort and easy to update; used to attach a $ estimate to each agent run.
Unknown models (including the offline `fake` model) estimate to $0.
"""
from __future__ import annotations

from .base import Usage

# model -> (input $/1M, output $/1M)
PRICING: dict[str, tuple[float, float]] = {
    "claude-opus-4-8": (5.0, 25.0),
    "claude-opus-4-7": (5.0, 25.0),
    "claude-opus-4-6": (5.0, 25.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.0),
    "gemini-2.0-flash": (0.10, 0.40),
}


def estimate_cost_usd(model: str, usage: Usage) -> float:
    rate = PRICING.get(model)
    if rate is None:
        return 0.0
    in_rate, out_rate = rate
    return round(
        usage.input_tokens / 1_000_000 * in_rate
        + usage.output_tokens / 1_000_000 * out_rate,
        6,
    )
