"""Day 6 — the portfolio site is served at / and embeds the live widget."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_root_serves_portfolio_with_demo_and_cta():
    with TestClient(app) as c:
        r = c.get("/")
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]
        body = r.text
        # embeds the same one-script-tag widget a client would add
        assert "/widget.js" in body
        # funnels to a single email CTA (no pricing tables)
        assert "mailto:chetansierra@gmail.com" in body
        # leads with the real eval proof
        assert "92.7" in body
