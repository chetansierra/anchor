# Anchor — AI Support & Action Agent

Anchor is a production-grade **website support agent**: it answers visitor
questions grounded in a real knowledge base — **with citations** — and takes
**real actions** (capture a lead, book a callback) that post to a CRM. It's built
to be **evaluated**, **observable**, and **provider-swappable**.

The bundled demo knowledge base is *Nimbus*, a fictional B2B SaaS product; point
it at your own docs and it works the same way.

> 📐 See [ARCHITECTURE.md](ARCHITECTURE.md) for the folder map, tech stack, and
> request flows.

## Features

- **The landing page is itself an AI agent.** An *AI solutions consultant*
  (`POST /consult/stream`) takes a free-form problem, classifies it into the
  productized services, answers grounded in a corpus about the work, **streams its
  reasoning as named stages over SSE**, and returns a structured mini-proposal —
  matched services, a tailored solution sketch, a rough timeline, and lead capture
  + proof. The [`web/`](web/) Next.js + Tailwind front-end renders it; the demo
  scoping your project is itself an example of the work. (Runs keyless too.)
- **Grounded RAG answers with citations.** Retrieves the most relevant
  knowledge-base chunks and answers from them, citing sources inline.
- **Real actions, not just chat.** A tool-calling agent can `capture_lead` and
  `book_callback`, writing to a mock CRM (an append-only JSONL sink that stands in
  for Airtable / HubSpot / a Sheet); review captures at `GET /leads`.
- **Provider-agnostic LLM.** One interface, swappable at runtime
  (`LLM_PROVIDER=auto|anthropic|openai|gemini|fake`) — Anthropic Claude by
  default. A keyless **fake** provider lets the app and the full test suite run
  with **no API key**.
- **Semantic retrieval, offline-capable.** Local `fastembed` (BGE) embeddings —
  free, no key — with a dependency-free lexical fallback so it always runs.
- **Won't hallucinate.** A two-layer guardrail: a retrieval-confidence backstop
  plus a grounding instruction that makes the model decline when the sources
  don't cover the question.
- **Observable.** Every `/chat` response includes tokens, **$ cost**, latency, the
  retrieved chunks, and any tool calls — and every run is persisted as a trace you
  can replay in the built-in `/admin` dashboard, with a daily cost rollup.
- **Embeddable in one line.** A single `<script>` tag drops a floating chat widget
  onto any site, **shadow-DOM isolated** so it never clashes with the host page;
  themeable via `data-` attributes, with a "Show how it works" toggle that reveals
  retrieval, cost, and tool calls.
- **Rate-limited & cost-capped.** The open demo is protected by a per-IP rate limit
  and a **hard daily cost ceiling** so a bot or bored visitor can't run up the bill;
  an optional API-key gate is the seam to per-client keys.
- **Evaluated.** A built-in harness scores answer correctness (LLM-as-judge),
  retrieval hit-rate, refusal correctness, and tool-call correctness.

## Quickstart

```bash
make install          # venv + core deps (runs with no API key)
make install-embed    # recommended: local semantic embeddings (fastembed/BGE)
make ingest           # build the knowledge-base index
make test             # run the test suite (keyless)
make run              # serve at http://127.0.0.1:8000/docs
```

For real LLM answers, add a key to `.env` (otherwise it runs on the keyless fake
provider):

```bash
echo "ANTHROPIC_API_KEY=sk-ant-..." >> .env
```

## API

| Endpoint | Purpose |
|---|---|
| `GET /` | portfolio landing page (hero, services, live demo, case study) |
| `GET /health` | status, loaded index, active provider/model |
| `POST /ingest` | (re)build the KB index from `data/kb/` |
| `POST /query` | raw retrieval — top-k chunks for a query |
| `GET /kb` | the documents the agent can answer from (titles + chunk counts) |
| `POST /chat` | the support agent — grounded answer + citations + actions |
| `POST /consult/stream` | the AI solutions consultant — SSE staged reasoning, then a structured proposal |
| `POST /consult/lead` | capture a lead from the consultant CTA into the mock CRM |
| `GET /consult/catalog` | the productized service catalog the consultant maps onto |
| `GET /leads` | recent leads / callbacks captured by the agent |
| `GET /admin` | observability dashboard (cost, latency, conversation traces) |
| `GET /admin/overview` | rollup: total/daily cost, tokens, escalation rate |
| `GET /admin/conversations[/{id}]` | recent runs (filter `?outcome=`) + full trace |
| `GET /widget.js` | the embeddable chat widget (one `<script>` tag) |
| `GET /demo` | a throwaway host page with the widget embedded |

```bash
curl -s -X POST localhost:8000/chat -H 'content-type: application/json' \
  -d '{"message":"do you support SAML SSO, and can someone call me about it?","top_k":3}'

curl -s localhost:8000/leads
```

## Configuration

All via environment variables or a local `.env` (every value has a default; the
defaults run keyless):

| Var | Default | Purpose |
|---|---|---|
| `LLM_PROVIDER` | `auto` | `auto` \| `anthropic` \| `openai` \| `gemini` \| `fake` |
| `ANTHROPIC_API_KEY` | – | enables real Claude answers |
| `ANTHROPIC_MODEL` | `claude-opus-4-8` | e.g. `claude-sonnet-4-6` / `claude-haiku-4-5` |
| `ANTHROPIC_THINKING` | `disabled` | `disabled` \| `adaptive` |
| `OPENAI_API_KEY` / `OPENAI_MODEL` | – / `gpt-4o-mini` | use OpenAI |
| `GEMINI_API_KEY` / `GEMINI_MODEL` | – / `gemini-2.0-flash` | use Gemini |
| `EMBEDDER` | `auto` | `auto` \| `fastembed` \| `openai` \| `hashing` |
| `MIN_CONFIDENCE` | `0.15` | low-confidence escalation backstop |
| `MAX_TOOL_ITERATIONS` | `4` | agent loop cap |
| `CORS_ALLOW_ORIGINS` | `*` | comma-separated origins allowed to call the API (set to your front-end origin in prod) |
| `FREELANCER_NAME` | `Chetan` | name the consultant introduces itself as |
| `CONSULT_TOP_K` | `5` | services-corpus chunks retrieved per consultation |
| `RATE_LIMIT_PER_MINUTE` | `20` | per-IP cap on `/chat` and `/consult/*` |
| `DAILY_COST_CEILING_USD` | `5.0` | hard daily `/chat` spend cap (from recorded traces) |
| `DEMO_API_KEY` | – | if set, `/chat` requires this `X-API-Key` header |

OpenAI/Gemini SDKs are optional: `pip install -r requirements-optional.txt`.
**Re-run `make ingest` after changing the embedder** (vector dimensions differ).

## Evaluation

`make eval` scores the agent over a labeled dataset (`data/eval/dataset.jsonl`)
and prints accuracy with a failure breakdown — a regression gate for a
non-deterministic system. It measures retrieval hit-rate, answer correctness
(LLM-as-judge against a rubric), refusal correctness on out-of-scope questions,
and tool-call correctness.

Representative run (Claude Sonnet 4.6, 41 cases):

| Metric | Result |
|---|---|
| Overall accuracy | 92.7% |
| Retrieval hit-rate | 100% |
| Refusal correctness (out-of-scope) | 8/8 |
| Tool-call correctness | 6/6 |
| Cost / run | ~$0.39 |

```bash
make eval                                    # full report (needs an API key)
python -m scripts.eval_cli ans-2fa-2 ans-sso-2   # re-run specific case ids
```

The harness runs on the keyless fake provider for CI plumbing; real numbers need
an API key.

## Observability

Every `/chat` run is persisted as a trace — question, answer, outcome, retrieved
chunks with scores, tool calls, tokens, **$ cost**, and latency. Inspect them two
ways:

```bash
open http://127.0.0.1:8000/admin   # dashboard: cost/latency cards, daily rollup,
                                   # click any conversation for its full trace
make costs                         # the same rollup in the terminal
```

So you can answer the two questions every client asks — *"can I see what it did?"*
and *"what will this cost me to run?"* — from real recorded runs.

## Embed on any site

One script tag mounts the agent as a floating chat widget, isolated in a shadow
root so it can't clash with the host page:

```html
<script src="https://YOUR_HOST/widget.js"
        data-business="Nimbus"
        data-color="#6ea8fe"
        data-position="bottom-right"
        data-machinery="off"></script>
```

| Attribute | Default | Purpose |
|---|---|---|
| `data-business` | from `/widget/config` | name shown in the header / greeting |
| `data-color` | `#6ea8fe` | brand accent color |
| `data-position` | `bottom-right` | `bottom-right` \| `bottom-left` |
| `data-machinery` | `off` | start with the "Show how it works" panel on |
| `data-api` | script origin | API base URL (set when hosted elsewhere) |

Run `make run` and open <http://127.0.0.1:8000/demo> (or `examples/embed-test.html`)
to see it live. The open demo is protected by a per-IP rate limit and a hard daily
cost ceiling (`RATE_LIMIT_PER_MINUTE`, `DAILY_COST_CEILING_USD`).

## Front-end (the consultant landing page)

The consultant experience is a separate **Next.js + Tailwind** app in [`web/`](web/)
that calls this backend directly over CORS (no proxy, so per-IP limits keep
working). `make ingest` builds **both** corpora (Nimbus support + services); then:

```bash
cd web && npm install
NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000 npm run dev   # http://localhost:3000
```

Deploy the front-end on Vercel and the backend on Railway/Fly/Render; set
`NEXT_PUBLIC_API_BASE` to the backend origin and `CORS_ALLOW_ORIGINS` to the
front-end origin. The vanilla portfolio + Nimbus widget stay served by FastAPI.

## Tests & CI

The suite runs **keyless** — a deterministic fake provider stands in for the LLM,
so `make test` (and CI on every push: install → ingest → pytest) needs no API key.
The front-end has its own keyless component tests (`cd web && npm run test`).

## Deployment

The `Dockerfile` builds a deploy-ready image (Railway / Fly.io / Render). The
index is built at image-build time so `/chat` works on first boot; inject `PORT`
and your provider key as environment variables.
