"""Day 5 — public-demo guardrails + the embeddable widget surface (keyless).

Covers what protects the open demo and what makes the one-script-tag embed work:
  1. the per-IP rate limiter slides its 60s window correctly,
  2. enforce_demo_limits gates on API key, rate, and the daily cost ceiling,
  3. the daily ceiling reads back today's recorded trace costs,
  4. /widget.js, /widget/config, and /demo serve the embed.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.agent import AgentResult
from app.config import Settings
from app.limits import RateLimiter, enforce_demo_limits
from app.llm.base import Usage
from app.main import app
from app.traces import TraceStore


def _result(cost: float) -> AgentResult:
    return AgentResult(
        answer="ok", grounded=True, escalated=False,
        usage=Usage(10, 5), cost_usd=cost, latency_ms=1.0,
        provider="fake", model="fake-1", iterations=1,
    )


def test_rate_limiter_slides_its_window():
    rl = RateLimiter(per_minute=2)
    assert rl.allow("ip", now=0.0)
    assert rl.allow("ip", now=1.0)
    assert not rl.allow("ip", now=2.0)   # 3rd hit inside 60s -> blocked
    assert rl.allow("ip", now=61.0)      # the t=0 hit has aged out -> allowed again
    # limiter is per-key
    assert rl.allow("other-ip", now=2.0)


def test_enforce_api_key_seam(tmp_path):
    settings = Settings(demo_api_key="secret")
    store = TraceStore(tmp_path)
    for bad in (None, "wrong"):
        with pytest.raises(HTTPException) as e:
            enforce_demo_limits(ip="a", api_key=bad, settings=settings,
                                limiter=RateLimiter(10), store=store)
        assert e.value.status_code == 401


def test_enforce_rate_limit(tmp_path):
    settings = Settings(traces_dir=str(tmp_path))
    store = TraceStore(tmp_path)
    limiter = RateLimiter(per_minute=1)
    enforce_demo_limits(ip="a", api_key=None, settings=settings, limiter=limiter, store=store)
    with pytest.raises(HTTPException) as e:
        enforce_demo_limits(ip="a", api_key=None, settings=settings, limiter=limiter, store=store)
    assert e.value.status_code == 429


def test_enforce_daily_cost_ceiling(tmp_path):
    settings = Settings(traces_dir=str(tmp_path), daily_cost_ceiling_usd=5.0)
    store = TraceStore(tmp_path)
    store.record("q1", _result(3.0))
    store.record("q2", _result(2.5))  # today's total now 5.5 >= 5.0
    assert store.cost_today() == pytest.approx(5.5)
    with pytest.raises(HTTPException) as e:
        enforce_demo_limits(ip="a", api_key=None, settings=settings,
                            limiter=RateLimiter(100), store=store)
    assert e.value.status_code == 429


def test_under_ceiling_and_limit_passes(tmp_path):
    settings = Settings(traces_dir=str(tmp_path), daily_cost_ceiling_usd=5.0, demo_api_key="k")
    store = TraceStore(tmp_path)
    store.record("q1", _result(0.5))
    # correct key, under ceiling, fresh limiter -> no exception
    enforce_demo_limits(ip="a", api_key="k", settings=settings,
                        limiter=RateLimiter(10), store=store)


def test_widget_routes_serve_the_embed():
    with TestClient(app) as c:
        js = c.get("/widget.js")
        assert js.status_code == 200
        assert "javascript" in js.headers["content-type"]
        assert "attachShadow" in js.text  # the shadow-DOM widget

        cfg = c.get("/widget/config").json()
        assert cfg["business"]
        assert isinstance(cfg["suggested"], list) and cfg["suggested"]

        demo = c.get("/demo")
        assert demo.status_code == 200
        assert "/widget.js" in demo.text


def test_kb_lists_the_documents_the_agent_knows():
    with TestClient(app) as c:
        kb = c.get("/kb").json()
        assert kb["business"]
        assert kb["count"] >= 1
        assert kb["count"] == len(kb["documents"])
        doc = kb["documents"][0]
        assert doc["title"] and doc["doc_id"] and doc["chunks"] >= 1
