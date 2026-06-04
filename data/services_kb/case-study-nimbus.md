# Case study — Nimbus support agent (the proof)

Nimbus is a fictional B2B SaaS help center I used to build and evaluate a real website support agent end to end. It's the live demo on this site and the proof that this engine works — the numbers below are the format I bring to your project.

## The build

A RAG support agent over 22 help-center documents: grounded answers with citations, two real actions (`capture_lead` and `book_callback`) writing to a mock CRM, anti-hallucination guardrails, an embeddable one-script-tag widget, per-run cost/latency observability, and rate-limiting plus a daily cost ceiling on the public demo.

## The evaluation (this is the differentiator)

Scored on 41 labeled question/answer cases, including out-of-scope questions it should refuse:

- **Overall answer accuracy: 92.7%** (LLM-as-judge with a rubric).
- **Retrieval hit-rate: 100%** — the right source was always retrieved.
- **Refusal correctness: 8/8** — it declined every out-of-scope question instead of guessing.
- **Tool-call correctness: 6/6** — right tool, right arguments.
- **Cost per run: a fraction of a cent** on a small model; every run is traced.

## What the eval caught

Running the eval surfaced bugs that "looks fine" testing never would: prompt context was being truncated and cutting off answer details, and tool guidance needed to be more prescriptive so the model picked a single correct action. Those fixes are why the accuracy number is real.

## Why it matters for you

You don't just get an agent — you get a measured one, plus a dashboard showing what each conversation costs. When a stakeholder asks "how do we know it's accurate and what does it cost to run?", there's a number.
