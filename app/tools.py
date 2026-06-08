"""Agent tools and how they record leads.

The tools normalize their arguments and write captured leads into the LeadStore
(Postgres in production, JSONL locally) tagged with source="chat". Descriptions
stay prescriptive about *when* to call each tool — recent models reach for tools
conservatively otherwise.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .leads import LeadStore
from .llm import ToolSpec


@dataclass
class Tool:
    spec: ToolSpec
    run: Callable[[dict], str]


def build_registry(store: LeadStore) -> dict[str, Tool]:
    """The agent's tool surface — both actions write a lead into the store."""

    def _confirm(lead: dict, label: str) -> str:
        return f"{label}. Reference: {lead['id']}. A team member will follow up."

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
        run=lambda args: _confirm(
            store.add(
                "chat",
                {
                    "email": args.get("email"),
                    "problem": args.get("reason"),
                    "name": args.get("name"),
                },
            ),
            "Lead captured",
        ),
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
        run=lambda args: _confirm(
            store.add(
                "chat",
                {
                    "contact": args.get("contact"),
                    "problem": args.get("topic"),
                    "name": args.get("name"),
                    "preferred_time": args.get("preferred_time"),
                },
            ),
            "Callback booked",
        ),
    )

    return {t.spec.name: t for t in (capture_lead, book_callback)}
