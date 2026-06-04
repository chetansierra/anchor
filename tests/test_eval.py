"""Keyless plumbing tests for the eval harness.

Verifies verdict parsing, per-category scoring, and report aggregation using the
deterministic FakeProvider as both agent and judge — no API key, CI-safe.
"""
from __future__ import annotations

from app.agent import Agent, AgentResult, ToolInvocation
from app.config import Settings
from app.embeddings import HashingEmbedder
from app.eval import EvalCase, Judge, format_report, run_eval, score_case
from app.eval.judge import parse_verdict
from app.ingest import run_ingest
from app.llm.base import LLMResponse, Usage
from app.llm.fake_provider import FakeProvider
from app.retrieval import Retriever
from app.tools import MockCRM


def _pass(reason="ok"):
    return LLMResponse(text=f"VERDICT: PASS\nREASON: {reason}", usage=Usage(30, 8))


def _fail(reason="missing detail"):
    return LLMResponse(text=f"VERDICT: FAIL\nREASON: {reason}", usage=Usage(30, 8))


def _agent(tmp_path, **overrides) -> Agent:
    settings = Settings(
        index_dir=str(tmp_path / "index"),
        crm_dir=str(tmp_path / "crm"),
        embedder="hashing",
        **overrides,
    )
    emb = HashingEmbedder(settings.hashing_dim)
    run_ingest(settings, embedder=emb)
    retriever = Retriever.load(settings, embedder=emb)
    return Agent(retriever, FakeProvider(), settings, MockCRM(settings.crm_path))


def test_parse_verdict():
    assert parse_verdict("VERDICT: PASS\nREASON: looks right").passed is True
    assert parse_verdict("verdict: fail\nreason: nope").passed is False
    assert parse_verdict("garbage").passed is False  # defaults to fail


def test_score_case_action_checks_tool():
    judge = Judge(FakeProvider())  # not consulted for action cases
    result = AgentResult(
        answer="done",
        grounded=True,
        escalated=False,
        tool_calls=[ToolInvocation("capture_lead", {"email": "a@b.com"}, "ok")],
    )
    good = EvalCase("t", "action", "contact me", None, False, "capture_lead", "records lead")
    bad = EvalCase("t", "action", "contact me", None, False, "book_callback", "books call")
    assert score_case(good, result, judge).primary_pass is True
    assert score_case(bad, result, judge).primary_pass is False


CASES = [
    EvalCase("a1", "answerable", "How do I reset my password?", "reset-password", False, None, "reset link"),
    EvalCase("o1", "out_of_scope", "What is the capital of France?", None, True, None, "declines"),
    EvalCase("t1", "action", "Please contact me at sam@acme.com about pricing", None, False, "capture_lead", "records lead"),
]


def test_run_eval_aggregates(tmp_path):
    agent = _agent(tmp_path, min_confidence=0.0)
    judge = Judge(FakeProvider(script=[_pass(), _pass()]))  # answerable + oos
    report = run_eval(agent, judge, CASES)

    assert report.total == 3
    assert report.overall_accuracy == 1.0
    assert report.by_category["action"]["pass"] == 1
    assert report.retrieval_hit_rate == 1.0  # reset-password retrieved for a1
    assert report.failures == []
    assert "ANCHOR EVAL" in format_report(report)


def test_run_eval_records_failures(tmp_path):
    agent = _agent(tmp_path, min_confidence=0.0)
    judge = Judge(FakeProvider(script=[_fail("no reset steps"), _pass()]))
    report = run_eval(agent, judge, CASES)

    assert report.overall_accuracy < 1.0
    assert any(f["id"] == "a1" for f in report.failures)
