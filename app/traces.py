"""Per-run observability: trace store + rollups.

Every `/chat` run is appended here as one JSON line — the full picture an
operator needs to answer "what happened, how long, how much": question, answer,
outcome, retrieved chunks (with scores), tool calls, token usage, $ cost, and
latency. The /admin view reads these back; the cost CLI rolls them up by day.

Append-only JSONL, mirroring the MockCRM sink — no database to stand up, and the
file is trivially greppable. Writes are best-effort: a trace failure must never
break a live answer.
"""
from __future__ import annotations

import json
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .agent import AgentResult


def _outcome(result: AgentResult) -> str:
    """Coarse label used to filter the admin view and flag runs worth a look."""
    if result.escalated:
        return "escalated"
    if any(t.result.startswith("Error") for t in result.tool_calls):
        return "error"
    return "answered"


def build_trace(question: str, result: AgentResult) -> dict:
    """Project an AgentResult into a flat, self-contained trace record."""
    return {
        "id": f"trace_{uuid.uuid4().hex[:10]}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "question": question,
        "answer": result.answer,
        "outcome": _outcome(result),
        "grounded": result.grounded,
        "escalated": result.escalated,
        "provider": result.provider,
        "model": result.model,
        "latency_ms": result.latency_ms,
        "usage": {
            "input_tokens": result.usage.input_tokens,
            "output_tokens": result.usage.output_tokens,
        },
        "cost_usd": result.cost_usd,
        "iterations": result.iterations,
        "tool_calls": [
            {"name": t.name, "arguments": t.arguments, "result": t.result}
            for t in result.tool_calls
        ],
        "citations": result.citations,
        "retrieved": result.retrieved,
    }


def _summary(trace: dict) -> dict:
    """A compact row for the conversations list (drops the heavy retrieved text)."""
    return {
        "id": trace["id"],
        "created_at": trace["created_at"],
        "question": trace["question"],
        "outcome": trace["outcome"],
        "model": trace["model"],
        "latency_ms": trace["latency_ms"],
        "input_tokens": trace["usage"]["input_tokens"],
        "output_tokens": trace["usage"]["output_tokens"],
        "cost_usd": trace["cost_usd"],
        "tools": [t["name"] for t in trace["tool_calls"]],
    }


@dataclass
class Overview:
    total_runs: int
    total_cost_usd: float
    avg_cost_per_conversation: float
    avg_latency_ms: float
    total_input_tokens: int
    total_output_tokens: int
    outcomes: dict  # outcome -> count
    escalation_rate: float
    daily: list[dict]  # newest first: {date, runs, input_tokens, output_tokens, cost_usd, escalated}


class TraceStore:
    def __init__(self, traces_dir: Path) -> None:
        self.path = Path(traces_dir) / "traces.jsonl"

    def record(self, question: str, result: AgentResult) -> dict:
        trace = build_trace(question, result)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(trace, ensure_ascii=False) + "\n")
        return trace

    def all(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [
            json.loads(line)
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def recent(self, limit: int = 50, outcome: str | None = None) -> list[dict]:
        traces = self.all()
        if outcome:
            traces = [t for t in traces if t["outcome"] == outcome]
        return [_summary(t) for t in reversed(traces)][:limit]

    def get(self, trace_id: str) -> dict | None:
        for t in self.all():
            if t["id"] == trace_id:
                return t
        return None

    def overview(self) -> Overview:
        traces = self.all()
        runs = len(traces)
        total_cost = round(sum(t["cost_usd"] for t in traces), 6)
        total_latency = sum(t["latency_ms"] for t in traces)
        total_in = sum(t["usage"]["input_tokens"] for t in traces)
        total_out = sum(t["usage"]["output_tokens"] for t in traces)

        outcomes: dict[str, int] = defaultdict(int)
        for t in traces:
            outcomes[t["outcome"]] += 1

        by_day: dict[str, dict] = defaultdict(
            lambda: {"runs": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "escalated": 0}
        )
        for t in traces:
            day = t["created_at"][:10]
            d = by_day[day]
            d["runs"] += 1
            d["input_tokens"] += t["usage"]["input_tokens"]
            d["output_tokens"] += t["usage"]["output_tokens"]
            d["cost_usd"] += t["cost_usd"]
            d["escalated"] += 1 if t["escalated"] else 0
        daily = [
            {"date": day, **{**v, "cost_usd": round(v["cost_usd"], 6)}}
            for day, v in sorted(by_day.items(), reverse=True)
        ]

        escalated = outcomes.get("escalated", 0)
        return Overview(
            total_runs=runs,
            total_cost_usd=total_cost,
            avg_cost_per_conversation=round(total_cost / runs, 6) if runs else 0.0,
            avg_latency_ms=round(total_latency / runs, 2) if runs else 0.0,
            total_input_tokens=total_in,
            total_output_tokens=total_out,
            outcomes=dict(outcomes),
            escalation_rate=round(escalated / runs, 4) if runs else 0.0,
            daily=daily,
        )
