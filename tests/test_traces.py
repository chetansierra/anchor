"""Day 4 observability — fully keyless.

Covers the trace store and the admin endpoints we must not regress on:
  1. a /chat run is recorded as a full, self-contained trace,
  2. outcome is derived correctly (answered / escalated / error),
  3. the overview rolls up cost, tokens, and escalations by day,
  4. the admin endpoints list, filter, fetch, and 404 as expected.
"""
from __future__ import annotations

import pytest

import app.main as main
from app.agent import AgentResult, ToolInvocation
from app.config import Settings
from app.llm.base import Usage
from app.traces import TraceStore, build_trace


def _answered() -> AgentResult:
    return AgentResult(
        answer="Click 'Forgot password?' [1].",
        grounded=True,
        escalated=False,
        citations=[{"n": 1, "doc_id": "reset-password", "title": "Reset", "source": "kb", "score": 0.7}],
        retrieved=[{"rank": 1, "doc_id": "reset-password", "title": "Reset", "source": "kb", "score": 0.7, "text": "..."}],
        usage=Usage(120, 30),
        cost_usd=0.0012,
        latency_ms=42.0,
        provider="fake",
        model="fake-1",
        iterations=1,
    )


def _escalated() -> AgentResult:
    return AgentResult(
        answer="I don't have enough information...",
        grounded=False,
        escalated=True,
        usage=Usage(0, 0),
        cost_usd=0.0,
        latency_ms=5.0,
        provider="fake",
        model="fake-1",
    )


def _errored() -> AgentResult:
    return AgentResult(
        answer="Logged your request.",
        grounded=True,
        escalated=False,
        tool_calls=[ToolInvocation("capture_lead", {"email": "x@y.com"}, "Error executing capture_lead: boom")],
        usage=Usage(80, 10),
        cost_usd=0.0005,
        latency_ms=33.0,
        provider="fake",
        model="fake-1",
        iterations=2,
    )


def test_build_trace_derives_outcome_and_keeps_full_picture():
    trace = build_trace("How do I reset my password?", _answered())
    assert trace["outcome"] == "answered"
    assert trace["question"] == "How do I reset my password?"
    assert trace["cost_usd"] == 0.0012
    assert trace["usage"] == {"input_tokens": 120, "output_tokens": 30}
    assert trace["retrieved"][0]["doc_id"] == "reset-password"  # full trace, not a summary
    assert trace["id"].startswith("trace_")

    assert build_trace("nonsense?", _escalated())["outcome"] == "escalated"
    assert build_trace("contact me", _errored())["outcome"] == "error"


def test_record_and_get_roundtrip(tmp_path):
    store = TraceStore(tmp_path)
    written = store.record("q", _answered())
    fetched = store.get(written["id"])
    assert fetched == written
    assert store.get("trace_missing") is None


def test_recent_is_newest_first_and_filterable(tmp_path):
    store = TraceStore(tmp_path)
    store.record("answered q", _answered())
    store.record("escalated q", _escalated())
    store.record("errored q", _errored())

    recent = store.recent()
    assert [r["question"] for r in recent] == ["errored q", "escalated q", "answered q"]
    assert "text" not in recent[0]  # summaries drop the heavy retrieved text
    assert recent[0]["tools"] == ["capture_lead"]

    assert [r["question"] for r in store.recent(outcome="escalated")] == ["escalated q"]
    assert len(store.recent(limit=1)) == 1


def test_overview_rolls_up_cost_tokens_and_escalations(tmp_path):
    store = TraceStore(tmp_path)
    store.record("a", _answered())
    store.record("b", _escalated())
    store.record("c", _errored())

    ov = store.overview()
    assert ov.total_runs == 3
    assert ov.total_input_tokens == 200  # 120 + 0 + 80
    assert ov.total_output_tokens == 40  # 30 + 0 + 10
    assert ov.total_cost_usd == pytest.approx(0.0017)
    assert ov.outcomes == {"answered": 1, "escalated": 1, "error": 1}
    assert ov.escalation_rate == pytest.approx(1 / 3, abs=1e-4)
    # all three recorded "now" -> a single day bucket holding every run
    assert len(ov.daily) == 1
    assert ov.daily[0]["runs"] == 3
    assert ov.daily[0]["escalated"] == 1
    assert ov.daily[0]["cost_usd"] == pytest.approx(0.0017)


def test_empty_overview_is_safe(tmp_path):
    ov = TraceStore(tmp_path).overview()
    assert ov.total_runs == 0
    assert ov.avg_cost_per_conversation == 0.0
    assert ov.daily == []


def test_admin_endpoints(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "get_settings", lambda: Settings(traces_dir=str(tmp_path)))
    store = TraceStore(tmp_path)
    written = store.record("answered q", _answered())
    store.record("escalated q", _escalated())

    overview = main.admin_overview()
    assert overview.total_runs == 2
    assert overview.escalation_rate == pytest.approx(0.5)

    convos = main.admin_conversations(limit=50, outcome=None)
    assert convos.count == 2
    assert convos.conversations[0].question == "escalated q"  # newest first

    escalated = main.admin_conversations(limit=50, outcome="escalated")
    assert escalated.count == 1

    full = main.admin_conversation(written["id"])
    assert full["retrieved"][0]["doc_id"] == "reset-password"

    with pytest.raises(Exception):  # HTTPException 404 for an unknown id
        main.admin_conversation("trace_missing")
