"""Durable lead storage + the admin surface — keyless (JSONL store, no DB)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import Settings
from app.leads import JsonlLeadStore, build_lead_store
from app.main import app


def _store(tmp_path) -> JsonlLeadStore:
    return JsonlLeadStore(str(tmp_path / "crm"))


def test_add_normalizes_and_routes_unknown_keys_to_meta(tmp_path):
    s = _store(tmp_path)
    lead = s.add(
        "consult",
        {
            "email": "a@co.com",
            "contact": "555-0100",
            "problem": "bot over docs",
            "services": ["rag_support_agent"],
            "name": "Al",  # not a column -> meta
        },
    )
    assert lead["source"] == "consult"
    assert lead["email"] == "a@co.com" and lead["contact"] == "555-0100"
    assert lead["services"] == ["rag_support_agent"]
    assert lead["meta"]["name"] == "Al"
    assert lead["status"] == "new" and lead["talk_to"] is None and lead["note"] is None


def test_recent_update_persists(tmp_path):
    s = _store(tmp_path)
    lead = s.add("consult", {"email": "a@co.com", "problem": "x"})

    updated = s.update(
        lead["id"], {"talk_to": True, "country": "IN", "note": "promising", "status": "contacted"}
    )
    assert updated is not None
    assert updated["talk_to"] is True and updated["country"] == "IN"
    assert updated["note"] == "promising" and updated["status"] == "contacted"
    assert updated["updated_at"]
    # re-read from disk
    assert s.recent()[0]["status"] == "contacted"
    # unknown id -> None
    assert s.update("lead_nope", {"status": "closed"}) is None


def test_recent_filters(tmp_path):
    s = _store(tmp_path)
    s.add("consult", {"email": "a@co.com", "problem": "chatbot over docs"})
    s.add("chat", {"email": "b@co.com", "problem": "pricing question"})

    assert len(s.recent(source="consult")) == 1
    assert len(s.recent(source="chat")) == 1
    assert len(s.recent(source="missing")) == 0
    hits = s.recent(q="pricing")
    assert len(hits) == 1 and hits[0]["email"] == "b@co.com"


def test_factory_defaults_to_jsonl_without_database_url(tmp_path):
    store = build_lead_store(Settings(crm_dir=str(tmp_path / "crm")))
    assert isinstance(store, JsonlLeadStore)


def test_consult_lead_then_admin_list_and_edit():
    with TestClient(app) as c:
        r = c.post("/consult/lead", json={"email": "z@co.com", "contact": "9", "problem": "x"})
        assert r.status_code == 200
        lead_id = r.json()["id"]

        listing = c.get("/leads?source=consult").json()
        assert any(row["id"] == lead_id for row in listing["leads"])

        up = c.patch(
            f"/admin/leads/{lead_id}",
            json={"talk_to": True, "status": "contacted", "country": "IN", "note": "hi"},
        )
        assert up.status_code == 200
        body = up.json()
        assert body["talk_to"] is True and body["status"] == "contacted"
        assert body["country"] == "IN" and body["note"] == "hi"

        page = c.get("/admin/leads")
        assert page.status_code == 200 and "Leads" in page.text


def test_admin_token_gate(monkeypatch):
    from app import main

    monkeypatch.setattr(main, "get_settings", lambda: Settings(admin_token="secret"))
    with TestClient(app) as c:
        assert c.get("/leads").status_code == 401
        ok = c.get("/leads", headers={"X-Admin-Token": "secret"})
        assert ok.status_code == 200
