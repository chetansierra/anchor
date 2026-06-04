# Anchor — Architecture

A production-grade **Website AI Support + Action Agent**: it answers questions
grounded in a real knowledge base (with citations) and takes real actions
(capture a lead / book a callback). Built to be **evaluated, observable, and
provider-swappable**.

## Tech stack

| Concern | Choice | Notes |
|---|---|---|
| Language / API | **Python 3.13 + FastAPI** | thin orchestration layer |
| Embeddings | **fastembed (BGE-small)**, local | offline `HashingEmbedder` fallback; OpenAI optional |
| Vector store | **numpy** `LocalVectorStore` (cosine) | swappable to pgvector/Qdrant |
| LLM | **Anthropic Claude** (default) | OpenAI / Gemini / keyless Fake behind one interface |
| Eval | **LLM-as-judge** + rubric | rolled into `make eval` |
| Tests / CI | **pytest** + GitHub Actions | runs keyless (no API key needed) |
| Packaging | **Dockerfile**, Makefile | deploy-ready image |

Everything external (embedder, LLM, vector store, CRM) sits behind a small
interface, so each can be swapped without touching the rest.

## Directory map

```
anchor/
├── app/                      # the application
│   ├── config.py             # env-driven settings (pydantic-settings); works keyless
│   ├── models.py             # FastAPI request/response schemas (pydantic)
│   ├── main.py               # FastAPI app: /health /ingest /query /chat /leads /admin /widget.js
│   │
│   ├── kb_loader.py          # load markdown KB docs from data/kb
│   ├── chunking.py           # token-aware chunking with overlap
│   ├── embeddings.py         # Embedder interface: hashing | fastembed | openai
│   ├── vectorstore.py        # VectorStore interface: numpy LocalVectorStore (cosine)
│   ├── ingest.py             # pipeline: load → chunk → embed → upsert → persist
│   ├── retrieval.py          # query-time: embed query → cosine search
│   ├── tools.py              # agent tools (capture_lead/book_callback) + mock CRM sink
│   ├── agent.py              # the agent loop (retrieve → ground → answer/cite or act)
│   ├── traces.py             # per-run trace store (JSONL) + cost/outcome rollups
│   ├── admin_page.py         # the /admin dashboard (one self-contained HTML page)
│   ├── limits.py             # public-demo guardrails: per-IP rate limit + daily $ ceiling
│   ├── static/               # widget.js (shadow-DOM chat widget) + embed-test.html
│   │
│   ├── llm/                  # provider-agnostic LLM layer (strategy pattern)
│   │   ├── base.py           #   normalized types + LLMProvider protocol
│   │   ├── anthropic_provider.py  # Claude: tool use + prompt caching (default)
│   │   ├── openai_provider.py     # OpenAI: function calling
│   │   ├── gemini_provider.py     # Gemini: function calling (best-effort)
│   │   ├── fake_provider.py       # deterministic, keyless — backs all tests
│   │   ├── factory.py             # build_llm_provider(): runtime selection
│   │   └── pricing.py             # per-model $ estimate from token usage
│   │
│   └── eval/                 # Day 3 eval harness
│       ├── dataset.py        #   load the labeled JSONL
│       ├── judge.py          #   LLM-as-judge (PASS/FAIL + reason)
│       ├── scorer.py         #   per-category scoring
│       └── runner.py         #   aggregate + format the report
│
├── data/
│   ├── kb/                   # ~22 seeded Nimbus help-center markdown docs (source)
│   ├── index/                # built vector index (generated, gitignored)
│   ├── crm/                  # mock CRM events.jsonl (generated, gitignored)
│   ├── traces/               # per-run traces.jsonl (generated, gitignored)
│   └── eval/dataset.jsonl    # 41 labeled eval cases (report.json is gitignored)
│
├── examples/                 # embed-test.html — paste-one-script-tag demo page
├── scripts/                  # CLIs: ingest_cli, retrieve_cli (acceptance), eval_cli, costs_cli
├── tests/                    # keyless pytest suite (retrieval, agent, translation, eval, traces, widget)
├── .github/workflows/ci.yml  # CI: install → ingest → pytest
├── Dockerfile                # deploy-ready image (Railway/Fly/Render)
├── Makefile                  # install / ingest / retrieve / run / test / eval / costs
└── ARCHITECTURE.md           # this file
```

## Components

- **config** — one `Settings` object (env or `.env`); chosen defaults run with no
  external services or keys. Derives the repo root from its own path, so the app
  is location-independent.
- **kb_loader / chunking / embeddings / vectorstore / ingest** — the RAG
  ingestion path. Docs → token-aware chunks → embeddings → a persisted numpy
  cosine index. Embedder and store are interfaces with swappable backends.
- **retrieval** — embeds a query (with the BGE instruction prefix) and returns the
  top-k chunks by cosine similarity.
- **llm** — the strategy layer. The agent depends only on the `LLMProvider`
  protocol and normalized message/tool types; each provider adapter converts to
  its native SDK. `LLM_PROVIDER` (`auto|anthropic|openai|gemini|fake`) picks the
  backend at runtime; `auto` ends at the keyless Fake so the app always starts.
- **tools** — the agent's actions and the mock CRM (an append-only JSONL sink
  standing in for a client's real CRM); an optional webhook mirrors events out.
- **agent** — the loop: retrieve → low-confidence guardrail → prompt the model
  with numbered sources + tools → answer with citations, or execute a tool and
  continue. Returns a structured result (answer, citations, tool calls, retrieved
  chunks, tokens, cost, latency).
- **eval** — runs the agent over the labeled dataset and grades it (retrieval
  hit-rate, answer correctness via LLM-as-judge, refusal correctness, tool
  correctness), emitting an accuracy report + failure breakdown.
- **traces** — observability sink. Each `/chat` run is appended to `traces.jsonl`
  (question, answer, outcome, retrieved chunks + scores, tool calls, tokens, $
  cost, latency) and rolled up by outcome and by day. Same append-only JSONL
  shape as the CRM — no database to run. The `costs_cli` reads it for the
  "what will this cost to run?" rollup.
- **admin_page** — the `/admin` dashboard: one dependency-free HTML page that
  calls the admin JSON endpoints and renders headline cost/latency cards, the
  daily cost rollup, and a click-to-expand list of recent conversations with
  their full trace.
- **limits** — public-demo guardrails for the open, keyless `/chat`: a per-IP
  sliding-window rate limiter and a hard daily $ ceiling (enforced by summing
  today's recorded trace costs, so it survives restarts), plus an optional
  `X-API-Key` gate — the seam that makes per-client keys / multi-tenant a small
  step later.
- **static/widget.js** — the embeddable widget: one `<script>` tag mounts a
  floating chat bubble in a **shadow root** (host CSS can't leak in or out),
  themeable via `data-` attributes. Suggested-prompt chips, visible tool actions,
  citations, and a "Show how it works" toggle (default off) that reveals the
  machinery — retrieved chunks + scores, latency, tokens, $ cost, tool-call JSON.
- **main** — the FastAPI surface tying it together; loads the index at startup,
  builds the agent lazily, enforces the demo guardrails and records a trace per
  `/chat`, serves the admin view, and serves the widget (`/widget.js`,
  `/widget/config`, `/demo`). CORS is enabled so the widget works cross-origin.

## Request flows

**Ingest** (`POST /ingest` or `make ingest`)
```
data/kb/*.md → kb_loader → chunking → embeddings.embed_documents
            → LocalVectorStore.upsert → persist to data/index/
```

**Chat** (`POST /chat`)
```
question → enforce_demo_limits (API-key seam → per-IP rate limit → daily $ ceiling)
        → retrieval.search (top-k)
        → guardrail: top score < MIN_CONFIDENCE? → escalate (no LLM call)
        → build prompt: static system (cached) + numbered SOURCES in user turn
        → LLMProvider.generate(tools=[capture_lead, book_callback])
        → tool_use? → tools.run → MockCRM.record → feed result back → loop
        → final answer + citations + tokens/cost/latency
        → TraceStore.record (best-effort; never blocks the answer)
```

**Widget** (`<script src=".../widget.js" data-...>` on any site)
```
script tag → mount shadow root → GET /widget/config (business + suggested chips)
          → user asks → POST /chat (CORS) → render answer + citations
          → tool call? → show "✅ Lead captured" action
          → "How it works" on? → reveal retrieved chunks + scores, cost, tokens, tool JSON
```

**Observe** (`GET /admin` + `make costs`)
```
data/traces/traces.jsonl → TraceStore.overview  → /admin/overview (cards + daily $ rollup)
                         → TraceStore.recent     → /admin/conversations (?outcome filter)
                         → TraceStore.get(id)    → /admin/conversations/{id} (full trace)
                         → scripts.costs_cli      → daily cost rollup in the terminal
```

**Eval** (`make eval`)
```
data/eval/dataset.jsonl → agent.run per case → scorer (judge for answer/refusal,
        retrieval hit, tool match) → aggregate → report (+ data/eval/report.json)
```

## Design patterns worth knowing

- **Seam at every vendor** — embedder, LLM, and vector store are interfaces.
- **Offline/keyless-first** — `HashingEmbedder` + `FakeProvider` let the app and
  the entire test suite run with no API key (fast, hermetic, free CI).
- **Two-layer hallucination guardrail** — a coarse retrieval-score gate (escalates
  without calling the model) plus the model's grounding instruction (the primary
  refusal layer).
- **Prompt caching discipline** — static system prompt + tools form the cached
  prefix; per-query retrieved context goes in the user turn.
