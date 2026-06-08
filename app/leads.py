"""Durable lead storage behind one interface.

Production uses Postgres (Neon) when ``DATABASE_URL`` is set; otherwise a local
append-only JSONL file — so local dev and the keyless test suite keep working
with no database. Both mirror to an optional outbound webhook (CRM_WEBHOOK_URL).

The schema is intentionally small with a ``meta`` JSONB catch-all, so new fields
cost nothing today and a real column is a one-line ALTER later.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from .config import Settings

# Fields an operator can edit from the admin (everything else is immutable).
EDITABLE_FIELDS = ("talk_to", "country", "note", "status")
# Filters the admin list accepts.
_FILTER_FIELDS = ("source", "status", "country")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_lead(source: str, fields: dict) -> dict:
    """Normalize a capture into the lead record shape. Unknown keys (e.g. a
    `name` or `preferred_time` from the chat tools) are tucked into `meta`."""
    f = dict(fields or {})
    return {
        "id": f"lead_{uuid.uuid4().hex[:8]}",
        "created_at": _now(),
        "source": source,
        "email": f.pop("email", None) or None,
        "contact": f.pop("contact", None) or None,
        "problem": f.pop("problem", None) or None,
        "services": f.pop("services", []) or [],
        "country": f.pop("country", None) or None,
        "talk_to": None,  # untriaged until an operator sets it
        "note": f.pop("note", None) or None,
        "status": "new",
        "updated_at": None,
        "meta": {k: v for k, v in f.items() if v is not None},
    }


def _apply_edits(lead: dict, changes: dict) -> dict:
    touched = False
    for key in EDITABLE_FIELDS:
        if key in changes:
            lead[key] = changes[key]
            touched = True
    if touched:
        lead["updated_at"] = _now()
    return lead


def _matches(lead: dict, filters: dict) -> bool:
    for key in _FILTER_FIELDS:
        want = filters.get(key)
        if want not in (None, "") and (lead.get(key) or "") != want:
            return False
    talk_to = filters.get("talk_to")
    if talk_to in (True, False) and lead.get("talk_to") is not talk_to:
        return False
    q = (filters.get("q") or "").strip().lower()
    if q:
        hay = " ".join(
            str(lead.get(k) or "") for k in ("email", "contact", "problem", "note")
        ).lower()
        if q not in hay:
            return False
    return True


def _mirror_webhook(url: str | None, lead: dict) -> None:
    if not url:
        return
    try:  # best-effort; never block a capture on the webhook
        import httpx

        httpx.post(url, json=lead, timeout=5.0)
    except Exception:
        pass


class LeadStore(Protocol):
    def ensure_schema(self) -> None: ...
    def add(self, source: str, fields: dict) -> dict: ...
    def recent(self, limit: int = 50, **filters) -> list[dict]: ...
    def update(self, lead_id: str, changes: dict) -> dict | None: ...


class JsonlLeadStore:
    """Append-only JSONL store — local dev + keyless tests (and a within-session
    backup if a Postgres write ever fails)."""

    def __init__(self, crm_dir: str | Path, webhook_url: str | None = None) -> None:
        self.path = Path(crm_dir) / "leads.jsonl"
        self.webhook_url = webhook_url

    def ensure_schema(self) -> None:
        return None

    def _all(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [
            json.loads(line)
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def add(self, source: str, fields: dict) -> dict:
        lead = _new_lead(source, fields)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(lead, ensure_ascii=False) + "\n")
        _mirror_webhook(self.webhook_url, lead)
        return lead

    def recent(self, limit: int = 50, **filters) -> list[dict]:
        rows = [r for r in reversed(self._all()) if _matches(r, filters)]
        return rows[:limit]

    def update(self, lead_id: str, changes: dict) -> dict | None:
        rows = self._all()
        updated: dict | None = None
        for r in rows:
            if r["id"] == lead_id:
                _apply_edits(r, changes)
                updated = r
        if updated is not None:
            self.path.write_text(
                "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                encoding="utf-8",
            )
        return updated


_COLUMNS = (
    "id", "created_at", "source", "email", "contact", "problem", "services",
    "country", "talk_to", "note", "status", "updated_at", "meta",
)

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS leads (
    id          TEXT PRIMARY KEY,
    created_at  TEXT NOT NULL,
    source      TEXT,
    email       TEXT,
    contact     TEXT,
    problem     TEXT,
    services    JSONB DEFAULT '[]'::jsonb,
    country     TEXT,
    talk_to     BOOLEAN,
    note        TEXT,
    status      TEXT DEFAULT 'new',
    updated_at  TEXT,
    meta        JSONB DEFAULT '{}'::jsonb
);
"""


class PostgresLeadStore:
    """Neon/Postgres store. ``psycopg`` is imported lazily so the package isn't
    required unless DATABASE_URL is actually set."""

    def __init__(self, dsn: str, webhook_url: str | None = None) -> None:
        self.dsn = dsn
        self.webhook_url = webhook_url

    def _connect(self):
        import psycopg  # lazy

        # Short-lived connections; Neon's -pooler endpoint handles pooling.
        return psycopg.connect(self.dsn)

    def ensure_schema(self) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(_CREATE_TABLE)
            conn.commit()

    def add(self, source: str, fields: dict) -> dict:
        from psycopg.types.json import Json

        lead = _new_lead(source, fields)
        params = [
            lead["id"], lead["created_at"], lead["source"], lead["email"],
            lead["contact"], lead["problem"], Json(lead["services"]),
            lead["country"], lead["talk_to"], lead["note"], lead["status"],
            lead["updated_at"], Json(lead["meta"]),
        ]
        placeholders = ", ".join(["%s"] * len(_COLUMNS))
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"INSERT INTO leads ({', '.join(_COLUMNS)}) VALUES ({placeholders})",
                params,
            )
            conn.commit()
        _mirror_webhook(self.webhook_url, lead)
        return lead

    def recent(self, limit: int = 50, **filters) -> list[dict]:
        from psycopg.rows import dict_row

        where: list[str] = []
        params: list = []
        for key in _FILTER_FIELDS:
            val = filters.get(key)
            if val not in (None, ""):
                where.append(f"{key} = %s")
                params.append(val)
        if filters.get("talk_to") in (True, False):
            where.append("talk_to = %s")
            params.append(filters["talk_to"])
        q = (filters.get("q") or "").strip()
        if q:
            where.append(
                "(coalesce(email,'') || ' ' || coalesce(contact,'') || ' ' || "
                "coalesce(problem,'') || ' ' || coalesce(note,'')) ILIKE %s"
            )
            params.append(f"%{q}%")
        clause = (" WHERE " + " AND ".join(where)) if where else ""
        params.append(limit)
        with self._connect() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"SELECT {', '.join(_COLUMNS)} FROM leads{clause} "
                "ORDER BY created_at DESC LIMIT %s",
                params,
            )
            return [dict(r) for r in cur.fetchall()]

    def update(self, lead_id: str, changes: dict) -> dict | None:
        from psycopg.rows import dict_row

        sets: list[str] = []
        params: list = []
        for key in EDITABLE_FIELDS:
            if key in changes:
                sets.append(f"{key} = %s")
                params.append(changes[key])
        if not sets:
            return self._get(lead_id)
        sets.append("updated_at = %s")
        params.append(_now())
        params.append(lead_id)
        with self._connect() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"UPDATE leads SET {', '.join(sets)} WHERE id = %s "
                f"RETURNING {', '.join(_COLUMNS)}",
                params,
            )
            row = cur.fetchone()
            conn.commit()
        return dict(row) if row else None

    def _get(self, lead_id: str) -> dict | None:
        from psycopg.rows import dict_row

        with self._connect() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"SELECT {', '.join(_COLUMNS)} FROM leads WHERE id = %s", [lead_id]
            )
            row = cur.fetchone()
        return dict(row) if row else None


def build_lead_store(settings: Settings) -> LeadStore:
    """Postgres when DATABASE_URL is set, else the local JSONL store."""
    if settings.database_url:
        return PostgresLeadStore(settings.database_url, settings.crm_webhook_url)
    return JsonlLeadStore(settings.crm_path, settings.crm_webhook_url)
