"""Day 2 agent behavior — fully keyless via the deterministic FakeProvider.

Covers the four things we must not regress on:
  1. grounded answers cite the right source,
  2. low-confidence questions escalate WITHOUT calling the model (no hallucination),
  3. a tool call actually writes a row to the mock CRM,
  4. the agent loop terminates at the iteration cap.
"""
from __future__ import annotations

from app.agent import Agent
from app.config import Settings
from app.embeddings import HashingEmbedder
from app.ingest import run_ingest
from app.llm.base import LLMResponse, ToolCall, Usage
from app.llm.fake_provider import FakeProvider
from app.retrieval import Retriever
from app.tools import MockCRM


def _settings(tmp_path, **overrides) -> Settings:
    return Settings(
        index_dir=str(tmp_path / "index"),
        crm_dir=str(tmp_path / "crm"),
        embedder="hashing",
        **overrides,
    )


def _agent(tmp_path, provider, **overrides) -> Agent:
    settings = _settings(tmp_path, **overrides)
    embedder = HashingEmbedder(settings.hashing_dim)
    run_ingest(settings, embedder=embedder)
    retriever = Retriever.load(settings, embedder=embedder)
    crm = MockCRM(settings.crm_path, settings.crm_webhook_url)
    return Agent(retriever, provider, settings, crm)


def test_grounded_answer_cites_correct_source(tmp_path):
    provider = FakeProvider(
        script=[
            LLMResponse(
                text="Click 'Forgot password?' and follow the emailed reset link [1].",
                stop_reason="end_turn",
                usage=Usage(120, 30),
            )
        ]
    )
    agent = _agent(tmp_path, provider, min_confidence=0.0)
    result = agent.run("How do I reset my password?")

    assert result.grounded is True
    assert result.escalated is False
    assert "[1]" in result.answer
    assert any(c["doc_id"] == "reset-password" for c in result.citations)
    assert result.usage.input_tokens == 120
    assert len(provider.calls) == 1


def test_out_of_scope_escalates_without_calling_model(tmp_path):
    provider = FakeProvider()  # would happily answer if it were called
    # A very high confidence bar guarantees the guardrail trips, independent of
    # the embedder's score for any particular phrase — we're testing that a
    # below-threshold retrieval escalates without ever invoking the model.
    agent = _agent(tmp_path, provider, min_confidence=0.99)
    result = agent.run("What is the airspeed velocity of an unladen swallow?")

    assert result.grounded is False
    assert result.escalated is True
    assert result.citations == []
    assert provider.calls == []  # the model is never invoked -> can't hallucinate


def test_tool_call_writes_lead_to_crm(tmp_path):
    provider = FakeProvider(
        script=[
            LLMResponse(
                tool_calls=[
                    ToolCall(
                        id="t1",
                        name="capture_lead",
                        arguments={
                            "name": "Jane",
                            "email": "jane@co.com",
                            "reason": "wants enterprise pricing",
                        },
                    )
                ],
                stop_reason="tool_use",
                usage=Usage(100, 10),
            ),
            LLMResponse(
                text="Thanks Jane — I've logged your request and our team will reach out [1].",
                stop_reason="end_turn",
                usage=Usage(40, 20),
            ),
        ]
    )
    agent = _agent(tmp_path, provider, min_confidence=0.0)
    result = agent.run("Can someone contact me about enterprise pricing?")

    assert len(provider.calls) == 2
    assert any(t.name == "capture_lead" for t in result.tool_calls)
    assert result.usage.input_tokens == 140  # 100 + 40 across both turns

    events = agent.crm.recent()
    assert len(events) == 1
    assert events[0]["type"] == "capture_lead"
    assert events[0]["fields"]["email"] == "jane@co.com"


def test_agent_loop_terminates_at_iteration_cap(tmp_path):
    looping = ToolCall(id="loop", name="capture_lead", arguments={"email": "loop@example.com"})
    provider = FakeProvider(always_tool=looping)
    agent = _agent(tmp_path, provider, min_confidence=0.0, max_tool_iterations=3)
    result = agent.run("Tell me about your pricing plans")

    assert len(provider.calls) == 3
    assert result.iterations == 3
    assert result.answer  # graceful fallback, not empty
