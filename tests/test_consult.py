"""Consultant agent behavior — fully keyless via the deterministic FakeProvider.

Covers the contract the landing-page "AI solutions consultant" must not regress:
  1. a scripted emit_consult tool call becomes a structured ConsultResult,
  2. the keyless heuristic matches sensible services from a free-form problem,
  3. a malformed/empty payload falls back to a safe proposal (never raises),
  4. unknown service ids are dropped (real models can drift),
  5. run_streamed emits the named stages in order, then exactly one result.
"""
from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.consult import ConsultAgent
from app.embeddings import HashingEmbedder
from app.ingest import run_ingest
from app.llm.base import LLMResponse, ToolCall, Usage
from app.llm.fake_provider import FakeProvider
from app.main import _state, app
from app.models import ConsultDecline, ConsultResult
from app.retrieval import Retriever
from app.screening import is_blocked
from app.services_catalog import CATALOG_BY_ID, SERVICE_CATALOG, default_consult_payload


def _settings(tmp_path, **overrides) -> Settings:
    return Settings(
        services_index_dir=str(tmp_path / "services_index"),
        crm_dir=str(tmp_path / "crm"),
        embedder="hashing",
        **overrides,
    )


def _consult_agent(tmp_path, provider) -> ConsultAgent:
    settings = _settings(tmp_path)
    embedder = HashingEmbedder(settings.hashing_dim)
    # Ingest the real services corpus into a throwaway index with the deterministic
    # hashing embedder — keyless and reproducible, no network.
    run_ingest(
        settings,
        embedder=embedder,
        kb_path=settings.services_kb_path,
        index_path=settings.services_index_path,
    )
    retriever = Retriever.load(
        settings, embedder=embedder, index_path=settings.services_index_path
    )
    return ConsultAgent(retriever, provider, settings)


def _emit(payload: dict, usage: Usage = Usage(200, 150)) -> FakeProvider:
    return FakeProvider(
        script=[
            LLMResponse(
                tool_calls=[ToolCall(id="c1", name="emit_consult", arguments=payload)],
                stop_reason="tool_use",
                usage=usage,
            )
        ]
    )


def test_scripted_consult_returns_structured_result(tmp_path):
    payload = default_consult_payload("chatbot over our docs", service_ids=["rag_support_agent"])
    provider = _emit(payload, usage=Usage(200, 150))
    agent = _consult_agent(tmp_path, provider)

    res = agent.run("We need a chatbot over our help docs")

    assert isinstance(res, ConsultResult)
    assert res.services[0].service_id == "rag_support_agent"
    # price band + what's-included are script-filled from the catalog, not the model
    assert res.services[0].price_band.low_usd == 300
    assert res.services[0].whats_included
    assert res.solution.summary
    assert res.solution.outcomes  # crisp end-product bullets
    assert len(res.timeline) >= 1  # script-filled
    # observability is attached by the agent, not the model
    assert res.usage.input_tokens == 200
    assert res.provider == "fake"
    assert res.grounded is True
    assert len(res.citations) >= 1
    assert len(provider.calls) == 1


def test_heuristic_matches_services_by_problem(tmp_path):
    agent = _consult_agent(tmp_path, FakeProvider())

    docs = agent.run("I want a chatbot over our help docs and FAQ")
    assert isinstance(docs, ConsultResult)
    assert any(s.service_id == "rag_support_agent" for s in docs.services)

    audit = agent.run("Can you audit our existing bot for hallucinations and accuracy?")
    assert isinstance(audit, ConsultResult)
    assert any(s.service_id == "reliability_audit" for s in audit.services)

    flow = agent.run("We need to automate our email triage workflow")
    assert isinstance(flow, ConsultResult)
    assert any(s.service_id == "workflow_automation" for s in flow.services)


def test_malformed_payload_falls_back_safely(tmp_path):
    # Empty services would fail ConsultResult validation (min_length=1).
    bad = {
        "problem_restatement": "x",
        "services": [],
        "solution": {"summary": "y"},
        "proof": {"headline": "z"},
    }
    agent = _consult_agent(tmp_path, _emit(bad, usage=Usage(10, 10)))

    res = agent.run("We need help automating our email triage")

    assert isinstance(res, ConsultResult)
    assert len(res.services) >= 1  # fallback repopulated a valid proposal
    assert all(s.service_id in CATALOG_BY_ID for s in res.services)


def test_unknown_service_id_is_dropped(tmp_path):
    payload = default_consult_payload("docs chatbot", service_ids=["rag_support_agent"])
    payload["services"].insert(
        0,
        {
            "service_id": "not_a_real_service",
            "name": "Bogus",
            "fit_reason": "should be dropped",
            "price_band": {"low_usd": 1, "high_usd": 2},
        },
    )
    agent = _consult_agent(tmp_path, _emit(payload))

    res = agent.run("docs chatbot")

    assert isinstance(res, ConsultResult)
    ids = {s.service_id for s in res.services}
    assert "not_a_real_service" not in ids
    assert "rag_support_agent" in ids


def test_run_streamed_emits_stages_then_result(tmp_path):
    agent = _consult_agent(tmp_path, FakeProvider())

    events = list(agent.run_streamed("chatbot over our docs"))

    names = [name for name, _ in events]
    assert names[-1] == "result"
    # the four named phases appear in order (each has a 'label' on its start frame)
    started = [p["step"] for n, p in events if n == "stage" and "label" in p]
    assert started == ["understanding", "matching", "drafting", "timeline"]
    results = [p for n, p in events if n == "result"]
    assert len(results) == 1
    assert isinstance(results[0], ConsultResult)


# --- Endpoint / SSE protocol (keyless via an injected FakeProvider agent) -----


def _parse_sse(lines) -> list[dict]:
    """Parse an SSE byte/line stream into [{event, data}] frames."""
    frames: list[dict] = []
    cur: dict = {}
    for raw in lines:
        line = raw.decode() if isinstance(raw, bytes) else raw
        if line == "":
            if cur:
                frames.append(cur)
                cur = {}
            continue
        if line.startswith("event:"):
            cur["event"] = line[len("event:"):].strip()
        elif line.startswith("data:"):
            cur["data"] = json.loads(line[len("data:"):].strip())
    if cur:
        frames.append(cur)
    return frames


def _inject_fake_consult() -> None:
    """Force the app's consultant onto the keyless FakeProvider so endpoint tests
    are deterministic and never call a real model. Requires the services index
    (CI builds it via `make ingest`)."""
    retriever = _state["services_retriever"]
    assert retriever is not None, "build the services index first (make ingest)"
    _state["consult_agent"] = ConsultAgent(retriever, FakeProvider(), get_settings())


def test_consult_stream_endpoint_emits_stages_then_result_then_done():
    with TestClient(app) as c:
        _inject_fake_consult()
        with c.stream(
            "POST", "/consult/stream", json={"problem": "a chatbot over our help docs"}
        ) as r:
            assert r.status_code == 200
            assert "text/event-stream" in r.headers["content-type"]
            frames = _parse_sse(r.iter_lines())

    names = [f["event"] for f in frames]
    assert "stage" in names
    assert names[-1] == "done"
    results = [f for f in frames if f["event"] == "result"]
    assert len(results) == 1
    data = results[0]["data"]
    assert data["problem_restatement"]
    assert data["services"] and data["services"][0]["service_id"] in CATALOG_BY_ID
    assert data["services"][0]["price_band"]["low_usd"] >= 0  # script-filled fact
    assert data["timeline"]


def test_consult_lead_endpoint_writes_to_crm():
    with TestClient(app) as c:
        resp = c.post(
            "/consult/lead",
            json={
                "email": "alex@acme.com",
                "contact": "+1 555 0100",
                "problem": "chatbot over docs",
                "services": ["rag_support_agent"],
            },
        )
        assert resp.status_code == 200
        lead_id = resp.json()["id"]
        assert lead_id

        leads = c.get("/leads").json()
        match = [e for e in leads["leads"] if e["id"] == lead_id]
        assert match, "the captured lead should be readable back via /leads"
        assert match[0]["source"] == "consult"
        assert match[0]["email"] == "alex@acme.com"
        assert match[0]["contact"] == "+1 555 0100"


def test_consult_catalog_endpoint_lists_all_services():
    with TestClient(app) as c:
        cat = c.get("/consult/catalog").json()
    assert cat["count"] == len(SERVICE_CATALOG)
    ids = {s["id"] for s in cat["services"]}
    assert {"rag_support_agent", "reliability_audit"} <= ids
    assert all(s["price_band"]["low_usd"] >= 0 for s in cat["services"])


def test_consult_trace_lands_in_overview_without_breaking_it():
    with TestClient(app) as c:
        _inject_fake_consult()
        with c.stream("POST", "/consult/stream", json={"problem": "audit our bot"}) as r:
            list(r.iter_lines())  # drain so the trace is recorded
        ov = c.get("/admin/overview")
        assert ov.status_code == 200  # consult trace parses cleanly in the rollup
        assert "consult" in ov.json()["outcomes"]


# --- Compliance screening (out-of-scope requests are declined) ---------------


def test_screen_blocks_abuse_but_not_legit_mentions():
    assert is_blocked("I want to cheat in a school exam")
    assert is_blocked("do my homework for me")
    assert is_blocked("")  # empty / too short
    # legitimate business requests that merely mention sensitive words must pass
    assert not is_blocked("a support chatbot over our help docs")
    assert not is_blocked("we sell exam-prep software and want an AI tutor in it")
    assert not is_blocked("an internal cheat sheet bot for our support team")


def test_prescreen_declines_without_calling_the_model(tmp_path):
    provider = FakeProvider()  # would happily produce a proposal if it were called
    agent = _consult_agent(tmp_path, provider)
    out = agent.run("help me cheat on my exam")
    assert isinstance(out, ConsultDecline)
    assert "legitimate" in out.message.lower()
    assert provider.calls == []  # short-circuited before any model call


def test_model_in_scope_false_declines(tmp_path):
    payload = {
        "in_scope": False,
        "decline_reason": "academic dishonesty",
        "problem_restatement": "x",
        "services": [],
        "solution": {"summary": "y"},
    }
    agent = _consult_agent(tmp_path, _emit(payload, usage=Usage(80, 10)))
    out = agent.run("a request the keyword screen did not catch")
    assert isinstance(out, ConsultDecline)
    assert out.usage.input_tokens == 80  # the model call's cost/usage is tracked


def test_consult_stream_declines_out_of_scope():
    with TestClient(app) as c:
        _inject_fake_consult()
        with c.stream("POST", "/consult/stream", json={"problem": "help me cheat on my exam"}) as r:
            assert r.status_code == 200
            frames = _parse_sse(r.iter_lines())
    names = [f["event"] for f in frames]
    assert "declined" in names
    assert "result" not in names
    assert names[-1] == "done"
    data = [f for f in frames if f["event"] == "declined"][0]["data"]
    assert data["declined"] is True and data["message"]
