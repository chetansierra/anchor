# AI lead-capture and booking agent

**Service id:** lead_capture_agent · **Typical price:** $400–1,000 (fixed scope)

Everything the support agent does, plus it **takes a real action**: when a visitor shares contact details, asks for pricing or a demo, or wants to talk to a person, the agent captures the lead or books a callback straight into your CRM, sheet, or inbox.

## When this fits

- You want the chatbot to convert, not just answer — capture leads, book calls, qualify prospects.
- You're paying for traffic and losing visitors who would have converted with a nudge.
- Sales wants every interested visitor logged with context, automatically.

## What's included

- A grounded support agent (RAG over your docs) as the base.
- Tool-calling with real webhooks into your CRM (HubSpot, Airtable, a Google Sheet, or a custom endpoint).
- Two actions out of the box — `capture_lead` and `book_callback` — with the agent choosing the right one and never spamming both.
- A "what just happened" confirmation so the visitor sees the action land (e.g. "Lead captured ✅").
- Observability: every captured lead is logged with the conversation context, cost, and latency.

## How it works under the hood

The agent runs a loop: retrieve grounding from your docs, decide whether to answer or call a tool, execute the tool (the webhook fires), feed the result back, and confirm to the visitor. The same loop powers the sales/email agents below.
