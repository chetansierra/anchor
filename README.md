# Anchor — AI Support & Action Agent

A production-grade **Website AI Support + Action Agent** built over a real
knowledge base — answers *anchored* to source docs (cited, grounded), plus
evaluated, observable, and provider-swappable. The demo business is *Nimbus*, a
fictional B2B SaaS team-workflow tool (non-fintech, swap freely).

Built incrementally, one focused milestone at a time.

## Day 1 — RAG ingestion + retrieval (done)

A working ingestion pipeline (`load → chunk → embed → upsert`) over a seeded KB,
plus an API to ingest and query it.

```
app/
  config.py        # env-driven settings (works with zero keys)
  chunking.py      # token-aware chunking with overlap
  embeddings.py    # Embedder interface: hashing (offline) | fastembed | openai
  vectorstore.py   # VectorStore interface: numpy LocalVectorStore (-> pgvector later)
  kb_loader.py     # load markdown docs from data/kb
  ingest.py        # the pipeline
  retrieval.py     # embed query -> cosine search
  main.py          # FastAPI: /health, /ingest, /query, /chat, /leads
data/kb/           # ~20 seeded Nimbus help-center docs
scripts/           # ingest_cli, retrieve_cli (acceptance check)
tests/             # hermetic retrieval regression test
```

## Day 2 — The agent core (done)

Retrieval becomes an **agent**: it answers **with citations** and takes a **real
action** (capture a lead / book a callback) that writes to a mock CRM.

```
app/
  llm/             # provider-agnostic LLM layer (strategy pattern)
    base.py        #   normalized types + LLMProvider protocol
    anthropic_provider.py  # Claude (tool use + prompt caching) — default
    openai_provider.py     # OpenAI (function calling)
    gemini_provider.py     # Gemini (best-effort; unverified without a key)
    fake_provider.py       # deterministic, keyless — backs all tests
    factory.py     #   build_llm_provider(): runtime selection via LLM_PROVIDER
    pricing.py     #   per-model $ estimate
  tools.py         # capture_lead / book_callback + mock CRM (JSONL sink)
  agent.py         # retrieve -> ground -> answer+cite / tool-call loop + guardrail
```

**Provider-agnostic by design.** The agent depends only on the `LLMProvider`
interface. `LLM_PROVIDER` (`auto|anthropic|openai|gemini|fake`) chooses the
backend at runtime; `auto` falls back through the providers by which API key is
present, ending at the keyless `fake` provider — so the app (and CI) always runs
with **no key**. Anthropic (`claude-opus-4-8`) is the default; the static system
prompt + tool defs form the cached prefix, with per-query context in the user turn.

**Guardrail:** if the top retrieval score is below `MIN_CONFIDENCE`, the agent
refuses/escalates **without calling the model** — it can't hallucinate what it
never sends.

### Try the agent

```bash
# no key needed (uses the fake provider); set ANTHROPIC_API_KEY for real answers
curl -s -X POST localhost:8000/chat \
  -H 'content-type: application/json' \
  -d '{"message":"how do I reset my password?","top_k":3}'

curl -s -X POST localhost:8000/chat \
  -H 'content-type: application/json' \
  -d '{"message":"can someone call me back about enterprise pricing?"}'

curl -s localhost:8000/leads      # see the captured lead / booked callback
```

### Configuring the LLM

Set these in `.env` (all optional — defaults run keyless):

| Var | Default | Purpose |
|---|---|---|
| `LLM_PROVIDER` | `auto` | `auto` \| `anthropic` \| `openai` \| `gemini` \| `fake` |
| `ANTHROPIC_API_KEY` | – | required for `anthropic` (real answers) |
| `ANTHROPIC_MODEL` | `claude-opus-4-8` | e.g. `claude-haiku-4-5` for a cheaper demo |
| `ANTHROPIC_THINKING` | `disabled` | `disabled` \| `adaptive` |
| `OPENAI_API_KEY` / `OPENAI_MODEL` | – / `gpt-4o-mini` | for `openai` |
| `GEMINI_API_KEY` / `GEMINI_MODEL` | – / `gemini-2.0-flash` | for `gemini` |
| `MIN_CONFIDENCE` | `0.15` | low-confidence escalation threshold |
| `MAX_TOOL_ITERATIONS` | `4` | agent loop cap |

OpenAI/Gemini SDKs are optional: `pip install -r requirements-optional.txt`.

**Acceptance:** one `/chat` run answers from the docs *with a citation* **and**
another writes a row to the mock CRM (`/leads`). All covered by `make test`,
keyless.

### Quickstart

```bash
make install          # venv + core deps (no API key needed)
make install-embed    # optional: real local embeddings (fastembed)
make ingest           # build the KB index
make retrieve         # Day 1 acceptance: top-k for 5 hand-picked questions
make test             # run the test suite
make run              # serve API at http://127.0.0.1:8000/docs
```

### Try the API

```bash
curl -s localhost:8000/health
curl -s -X POST localhost:8000/ingest
curl -s -X POST localhost:8000/query \
  -H 'content-type: application/json' \
  -d '{"query":"how do I reset my password?","top_k":4}'
```

### Embeddings: zero-config by default

`EMBEDDER=auto` (the default) uses `fastembed` if installed, else OpenAI if
`OPENAI_API_KEY` is set, else a dependency-free **HashingEmbedder** — so it runs
offline with no keys. Retrieval stays free either way; only generation costs
money, which keeps the public demo cheap to run.

**Recommended: `make install-embed`** then `make ingest`. This switches `auto`
to real **semantic** embeddings (`fastembed`, BGE-small — local, no API key) and
markedly improves recall on paraphrased questions the lexical fallback misses
(e.g. *"I'm locked out and can't remember my login"* → the reset-password doc).
A short BGE query-instruction prefix is applied to queries for an extra boost.

Set `EMBEDDER` in `.env` to pin a backend. **Re-run `make ingest` whenever you
change the embedder** — vector dimensions differ (hashing 1024, BGE-small 384).

**Acceptance:** `make retrieve` prints PASS for all 5 hand-picked questions.
