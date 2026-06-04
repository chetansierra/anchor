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
  main.py          # FastAPI: /health, /ingest, /query
data/kb/           # ~20 seeded Nimbus help-center docs
scripts/           # ingest_cli, retrieve_cli (acceptance check)
tests/             # hermetic retrieval regression test
```

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
`OPENAI_API_KEY` is set, else a dependency-free **HashingEmbedder** — so Day 1
runs offline with no keys. Retrieval stays free; only generation (Day 2) costs
money, which keeps the public demo cheap to run. Set `EMBEDDER` in `.env` to pin
a backend. **Re-run `make ingest` whenever you change the embedder** (vector
dimensions change).

**Acceptance:** `make retrieve` prints PASS for all 5 hand-picked questions.
