# How I work — approach, process, and timeline

Every engagement follows the same shape, regardless of which service you pick. It's deliberately phased so you see progress early and there are no surprises.

## The phases

1. **Discovery & scoping (1–2 days).** We agree on the exact problem, success criteria, what data the agent uses, and which actions it takes. You get a fixed scope and price — no open-ended hourly drift.
2. **Ingestion & retrieval (1–3 days).** Load your docs/data, chunk and embed them, and stand up retrieval. Acceptance check: a query returns the right sources.
3. **Agent & actions (2–4 days).** Build the answer path with citations, add tool-calling for the real actions (capture lead, book call, internal API), and add the anti-hallucination guardrails.
4. **Evaluation (1–2 days).** Write labeled test cases over your domain and score accuracy, retrieval, and tool-calling. You get a report with a number, not a vibe.
5. **Observability & deploy (1–2 days).** Per-run traces (latency, tokens, cost), a small admin view, a daily cost rollup, rate-limiting and a cost ceiling, then deploy (the embeddable widget or an internal app).

## Typical timeline

A focused single agent (support or lead-capture) is usually **1–2 weeks** of part-time work end to end. Workflow automations are often faster (a few days to a week). Multi-step agentic roles and internal-tooling integrations run **2–3 weeks** depending on how many systems they touch.

## What I need from you

Your docs/content, access (or a sandbox) for any tools the agent integrates with, and a point of contact for the discovery call. That's usually enough to start.

## What makes the result hold up

Every external dependency sits behind an interface (LLM provider, embeddings, vector store, CRM), so nothing is locked to one vendor; there's a keyless test suite; and the agent is measured before it ships. That's the "doesn't break in production" part.
