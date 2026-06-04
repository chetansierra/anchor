"""Agent tools and the mock CRM they write to.

The mock CRM is an append-only JSONL file standing in for a client's real CRM /
inbox (the thing a paying client would wire to Airtable, HubSpot, a Sheet, etc.).
Tool actions write a row here; the demo's "what just happened" panel reads it
back via GET /leads. An optional webhook mirrors each event to an external URL.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .llm import ToolSpec


@dataclass
class Tool:
    spec: ToolSpec
    run: Callable[[dict], str]


class MockCRM:
    def __init__(self, crm_dir: Path, webhook_url: str | None = None) -> None:
        self.path = Path(crm_dir) / "events.jsonl"
        self.webhook_url = webhook_url

    def record(self, event_type: str, fields: dict) -> dict:
        event = {
            "id": f"lead_{uuid.uuid4().hex[:8]}",
            "type": event_type,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "fields": fields,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
        if self.webhook_url:
            self._post(event)
        return event

    def _post(self, event: dict) -> None:
        try:  # best-effort mirror; never block the agent on the webhook
            import httpx

            httpx.post(self.webhook_url, json=event, timeout=5.0)
        except Exception:
            pass

    def recent(self, limit: int = 20) -> list[dict]:
        if not self.path.exists():
            return []
        events = [
            json.loads(line)
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        return list(reversed(events))[:limit]


def build_registry(crm: MockCRM) -> dict[str, Tool]:
    """The agent's tool surface. Descriptions are prescriptive about *when* to
    call each tool — recent models reach for tools conservatively otherwise."""

    def _confirm(event: dict, label: str) -> str:
        return f"{label}. Reference: {event['id']}. A team member will follow up."

    capture_lead = Tool(
        spec=ToolSpec(
            name="capture_lead",
            description=(
                "Record a sales/support lead. Call this when the visitor shares "
                "their contact details or asks to be contacted, wants pricing or "
                "plan help, or wants to speak with a person."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "The person's name"},
                    "email": {"type": "string", "description": "Their contact email"},
                    "reason": {
                        "type": "string",
                        "description": "What they need or why they want to be contacted",
                    },
                },
                "required": ["email"],
            },
        ),
        run=lambda args: _confirm(crm.record("capture_lead", args), "Lead captured"),
    )

    book_callback = Tool(
        spec=ToolSpec(
            name="book_callback",
            description=(
                "Book a phone callback. Call this only when the visitor explicitly "
                "asks to schedule a call or speak with sales/support by phone."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "contact": {"type": "string", "description": "Phone number or email"},
                    "topic": {"type": "string", "description": "What the call is about"},
                    "preferred_time": {
                        "type": "string",
                        "description": "When they'd like to be called",
                    },
                },
                "required": ["contact"],
            },
        ),
        run=lambda args: _confirm(crm.record("book_callback", args), "Callback booked"),
    )

    return {t.spec.name: t for t in (capture_lead, book_callback)}
