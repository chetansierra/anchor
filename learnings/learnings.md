# Anchor — Build Learnings & Decisions Log

A running journal of how this project was built: the concepts worth remembering,
the mistakes we made (and how we fixed them), and the decisions and why.

**Conventions**
- **Append-only journal.** Add a new dated entry per phase/day at the bottom.
  Don't rewrite past entries — being able to see what we believed *then* is the
  point.
- The **Principles** section below is the one part we revise freely as our
  understanding sharpens.
- Engineering-focused and public-safe. Private strategy/business context lives in
  the gitignored `MAIN_GOAL.MD`, not here.

---

## Principles & recurring lessons (revise freely)

1. **Put a seam wherever a vendor lives.** Every external dependency (embedder,
   LLM, vector store, CRM) sits behind a small interface from day one. This is
   what later made the agent provider-swappable (Anthropic/OpenAI/Gemini) and let
   us upgrade retrieval (lexical → semantic) without touching the agent.
2. **Offline-first / keyless by default.** A free, local fallback for every paid
   dependency (HashingEmbedder for embeddings, FakeProvider for the LLM) means
   the app and the whole test suite run with **no API key**. CI stays fast,
   hermetic, and free; contributors aren't blocked on secrets.
3. **Test the mechanism, not a magic number.** Tests that assert on a specific
   model/embedder score are fragile. Assert the *behavior* (e.g. set the
   threshold so the guardrail must trip) deterministically instead.
4. **Retrieval success ≠ answer success.** The right doc reaching the retriever
   is necessary but not sufficient — how you *format and truncate* it into the
   prompt is its own failure mode. (The Day-3 eval proved this.)
5. **Measure before you optimize.** We deliberately skipped rerankers/hybrid
   search until the eval could tell us whether they were needed. The eval found
   the real bug was prompt truncation, not retrieval quality.
6. **Thresholds are embedder-dependent and weak.** A confidence score gate that
   works for one embedder misfires on another. Keep it a low backstop; make the
   model's grounding instruction the primary refusal mechanism.
7. **Scrub before you publish.** Public repos get cached/indexed. Remove
   sensitive docs from history *before* the first push, not after.
8. **A keyless fake is worth building well.** The FakeProvider (scriptable for
   tests, heuristic for local runs) paid for itself many times over.

---

## Journal (append-only)

### 2026-06-04 — Phase 0: Vision & scope

**Decisions**
- The **live demo is the product**: it must provoke a visitor to try it once and
  walk away convinced. Locked scope: **seeded data only** (no user uploads, no
  email gate) to keep the public surface simple and cheap.
- Three interaction moments: instant try, **visible actions** (a tool call the
  user can see happen), and a **"show how it works" toggle** (retrieval scores,
  latency, cost, tool-call JSON) — clean by default, proof on demand.
- Guardrail baked into the plan: a public demo calls a **paid LLM with no auth**,
  so it must be **rate-limited with a hard cost ceiling**.
- Picked a **non-fintech** fictional demo business — *Nimbus*, a B2B SaaS
  team-workflow tool — to keep the demo clear of any conflict of interest.

**Concept** — the differentiator isn't "I build agents" (crowded); it's
"production-grade agents on real data: evaluated, observable, swappable."

---

### 2026-06-04 — Phase 1: Ingestion & retrieval (Day 1)

**Built** — a RAG ingestion pipeline (`load → chunk → embed → upsert`) over ~22
seeded Nimbus help-center docs, plus a FastAPI surface (`/health`, `/ingest`,
`/query`).

**Concepts**
- **Token-aware chunking** (~500 tokens, with overlap), preferring sentence
  boundaries so we don't split mid-thought. Uses `tiktoken` if present, else a
  chars/token estimate — kept dependency-free.
- **Embedder behind an interface** with three backends: a zero-dependency
  `HashingEmbedder` (signed feature hashing of words + char-trigrams — lexical,
  but offline and deterministic), `fastembed` (local semantic), and OpenAI.
- **numpy `LocalVectorStore`**: L2-normalize vectors so cosine similarity is a
  single matrix-vector dot product. Transparent, fast for this size, swappable to
  pgvector/Qdrant later.

**Decisions** — Python + FastAPI; offline `HashingEmbedder` as the default so Day
1 runs with no keys; retrieval stays free (only generation costs money — supports
the cost-cap story).

**Acceptance** — 5/5 hand-picked questions returned the right source.

---

### 2026-06-04 — Project restructure & first public push

**What happened** — moved the whole project into an `anchor/` subfolder (the
`Freelance/` dir is a multi-project container), then `git init` + first public
GitHub repo.

**Mistakes & lessons**
- **Don't move a virtualenv.** venvs hardcode absolute paths (`pyvenv.cfg`,
  console-script shebangs), so a moved `.venv` breaks. Fix: **recreate** the venv
  in the new location (it's gitignored and cheap to rebuild). The app code needed
  *no* path changes because `config.py` derives the repo root from its own file
  location, not the cwd — a small design choice that paid off.
- **Scrub sensitive docs before going public.** `MAIN_GOAL.MD` contained private
  planning context. We gitignored it **and amended the initial commit** so it
  never entered the public history — public repos get cached/indexed, so removing
  after the fact isn't enough.

---

### 2026-06-04 — Phase 2: Agent core (Day 2)

**Built** — retrieval became an **agent**: grounded, cited answers plus real tool
actions (`capture_lead` / `book_callback`) that write to a mock CRM (JSONL sink),
readable via `/leads`. New `/chat` endpoint returns answer, citations, retrieved
chunks, tool calls, tokens, cost, and latency.

**Concepts**
- **Strategy pattern for the LLM.** One `LLMProvider` protocol + normalized types
  (`LLMMessage`, `ToolCall`, `ToolResult`, `LLMResponse`). Each adapter translates
  to/from its native SDK. Backends: Anthropic (default, tool use + prompt
  caching), OpenAI, Gemini (best-effort), and a keyless **FakeProvider**.
  `LLM_PROVIDER` selects at runtime; `auto` falls back by which key is present,
  ending at Fake.
- **Prompt caching done right for RAG.** The cacheable prefix is the *static*
  system prompt + tool definitions; the *per-query* retrieved context goes in the
  user turn. Putting volatile context after the cached prefix is what makes
  caching actually hit.
- **Two-layer hallucination guardrail.** (a) a coarse retrieval-score gate that
  escalates *without calling the model* (can't hallucinate what it never sends);
  (b) the model's own grounding instruction — the primary layer — which declines
  when the sources don't cover the question.
- **Keyless, pure translation tests.** The trickiest part of an adapter is the
  message/tool translation — and it's a *pure function*, so we unit-test it with
  no SDK and no key.

**Mistakes & fixes**
- **The fake heuristic read the wrong string.** Its "does the user want contact?"
  check scanned the entire user message — which includes the retrieved SOURCES —
  so source text like *"contact us"* false-triggered a tool call. Fix: detect
  intent only on the text after `"Customer question:"`. Lesson: be precise about
  what's actually inside the string you call "the question."
- **A fragile escalation test.** It depended on a specific embedder score for one
  phrase. Fix: assert the *mechanism* — set `min_confidence` high so the guardrail
  must trip — instead of a magic number. (See Principle 3.)
- **Observed (fixed in Day 3):** the model sometimes fired *both* `capture_lead`
  and `book_callback` for one request — redundant.

**Decisions**
- Default model `claude-opus-4-8` (configurable); later set to **Sonnet 4.6**
  ($3/$15 vs Opus $5/$25) as the cost/quality middle ground for the demo.
- Workflow: from Day 2 on, each unit of work is a **feature branch → PR → main**.
- Live run sanity check: real cost-per-query landed at **~$0.007–0.011** on
  Sonnet; the two-layer guardrail correctly refused an out-of-scope question even
  when retrieval returned (irrelevant) chunks.

---

### 2026-06-04 — Retrieval upgrade (lexical → semantic)

**Built** — installed `fastembed` (BGE-small, local, no key) so `auto` now picks
**semantic** embeddings instead of the lexical hashing fallback. Added the BGE
query-instruction prefix (applied to queries only).

**Evidence** — on a paraphrase set (questions worded nothing like the docs),
hashing got **4/6**, fastembed **6/6**. e.g. *"I'm locked out and can't remember
my login"* → reset-password.

**Lessons**
- **Confidence thresholds are embedder-specific.** BGE's similarity range is
  compressed (in-scope ~0.6, out-of-scope ~0.5), so a high score gate would
  misfire on valid paraphrases (~0.59). We keep the gate **low** as a backstop and
  rely on the model's grounding (Principle 6).
- **Changing the embedder changes the vector dimension** (hashing 1024 → BGE 384)
  — the index must be **re-ingested** after any embedder change. The store records
  the embedder + dim and raises a clear error on mismatch.
- **Resisted over-engineering** (no reranker/hybrid yet) — let the eval decide.

---

### 2026-06-04 — Phase 3: Eval harness (Day 3)

**Built** — a labeled set of **41 cases** (answerable / out-of-scope-should-refuse
/ action) scored on four axes — retrieval hit-rate, answer correctness
(**LLM-as-judge** vs. a rubric), refusal correctness, tool-call correctness — with
`make eval` and a per-id subset re-run. Plumbing is keyless (FakeProvider as both
agent and judge); real numbers need a key.

**Scorecard (Sonnet 4.6, 41 cases)** — overall **92.7%**, retrieval hit@k
**100%**, refusal **8/8**, tool **6/6**; ~$0.39/run.

**The big lesson — the eval found a bug we'd never have noticed.** All 3 failures
were `answerable` with **100% retrieval** — the right doc was found, but the answer
dropped a specific detail (e.g. "an admin can reset 2FA", "SSO disables password
login", "contact support with your invoice number"). Root cause: we **truncated
each source to 800 chars** when formatting the prompt, cutting off the tail of each
doc — exactly where those details lived. **Retrieval success ≠ answer success**
(Principle 4).

**3 fixes the eval drove**
1. **Context truncation** → raised the per-source char budget so full chunks reach
   the model (`source_char_budget`).
2. **Completeness instruction** in the system prompt — include caveats,
   prerequisites, and specifics, not just the headline.
3. **Single-tool guidance** — pick one tool (`book_callback` for phone, else
   `capture_lead`); don't fire both.
Re-checked live (subset re-run by case id, to control spend): the 3 cases pass and
the double-tool-call is gone.

**Concepts**
- **LLM-as-judge** for grading non-deterministic output against a rubric — the
  only practical way to regression-test answer quality.
- **Cheap verification.** Added an id filter to the eval CLI so we re-run *only*
  the affected cases instead of the full set — cost discipline matters when each
  run spends real money.
