"""Central configuration.

Everything is overridable via environment variables (or a local .env). Defaults
are chosen so Day 1 runs with zero external services or API keys.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root = parent of the `app/` package. Keeps paths stable regardless of the
# directory the process is launched from.
ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Demo business -------------------------------------------------------
    business_name: str = "Nimbus"

    # --- Paths (relative to repo root unless absolute) -----------------------
    kb_dir: str = "data/kb"
    index_dir: str = "data/index"

    # --- Chunking ------------------------------------------------------------
    chunk_target_tokens: int = 500
    chunk_overlap_tokens: int = 75
    chars_per_token: float = 4.0  # fallback estimate when tiktoken is absent

    # --- Retrieval -----------------------------------------------------------
    top_k: int = 4

    # --- Embeddings ----------------------------------------------------------
    # auto -> fastembed if importable, else openai if key set, else hashing.
    embedder: str = "auto"
    fastembed_model: str = "BAAI/bge-small-en-v1.5"
    # BGE-v1.5 retrieval instruction, prepended to queries only (boosts recall).
    fastembed_query_prefix: str = "Represent this sentence for searching relevant passages: "
    hashing_dim: int = 1024
    openai_embed_model: str = "text-embedding-3-small"
    openai_api_key: str | None = None

    # --- LLM / generation (Day 2) -------------------------------------------
    # Strategy selector: auto | anthropic | openai | gemini | fake
    #   auto -> anthropic if key set, else openai, else gemini, else fake.
    llm_provider: str = "auto"
    max_tokens: int = 1024

    # Anthropic (default provider). Model overridable; opus-4-8 is the default
    # per Anthropic guidance — set ANTHROPIC_MODEL=claude-haiku-4-5 for a cheaper
    # public demo. thinking: disabled | adaptive.
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-opus-4-8"
    anthropic_thinking: str = "disabled"

    # OpenAI (alternative provider; lazy-imported).
    openai_model: str = "gpt-4o-mini"

    # Gemini (alternative provider; lazy-imported).
    gemini_api_key: str | None = None
    google_api_key: str | None = None  # google-genai's native env var name
    gemini_model: str = "gemini-2.0-flash"

    # --- Agent behavior ------------------------------------------------------
    # Low-confidence guardrail (coarse backstop): below this top-1 score the
    # agent escalates WITHOUT calling the model. Kept low on purpose so it never
    # wrongly refuses valid queries on either embedder (hashing in-scope ~0.3+,
    # fastembed/BGE in-scope ~0.6+ — both well above 0.15; BGE's compressed
    # range puts out-of-scope at ~0.5, so a high gate would misfire). The PRIMARY
    # refusal layer is the model's grounding instruction, which declines when the
    # retrieved sources don't actually answer the question.
    min_confidence: float = 0.15
    max_tool_iterations: int = 4
    # Per-source char budget when formatting retrieved chunks into the prompt.
    # Must comfortably exceed a chunk so we don't drop the tail of a doc (the
    # Day 3 eval caught 800 cutting off answer details near the end of sources).
    source_char_budget: int = 1600

    # --- Mock CRM (tool action sink) ----------------------------------------
    crm_dir: str = "data/crm"
    crm_webhook_url: str | None = None  # optional: POST each event here too

    # --- Observability (Day 4) ----------------------------------------------
    # Per-run traces (latency, tokens, $, retrieved chunks, tool calls, outcome)
    # are appended here as JSONL; the /admin view and cost rollup read them back.
    traces_dir: str = "data/traces"

    # --- Embeddable widget + public-demo guardrails (Day 5) -----------------
    # The widget is one <script> tag; these protect the open, keyless demo from a
    # bot or bored visitor running up the API bill (a selling point in itself).
    cors_allow_origins: str = "*"  # comma-separated origins; "*" for the open demo
    rate_limit_per_minute: int = 20  # per client IP, on /chat
    # Hard daily $ ceiling on /chat — enforced by summing today's recorded trace
    # costs (Day 4), so it survives restarts. Above it, /chat declines politely.
    daily_cost_ceiling_usd: float = 5.0
    # Optional X-API-Key gate. Unset -> open demo; set -> required (the seam that
    # makes per-client keys / multi-tenant a small step later).
    demo_api_key: str | None = None

    # --- Consultant agent (the pivot / v2 hero) -----------------------------
    # A SECOND corpus, about the freelancer's OWN services, powers the
    # landing-page "AI solutions consultant": it classifies a visitor's problem
    # into the productized gigs and streams a tailored mini-proposal. Kept in its
    # own dir/index so the Nimbus support corpus (and its tests) stay untouched.
    services_kb_dir: str = "data/services_kb"
    services_index_dir: str = "data/services_index"
    consult_top_k: int = 5
    consult_max_tokens: int = 2048  # the structured card payload is larger than a chat answer
    freelancer_name: str = "Chetan"

    def path(self, value: str) -> Path:
        p = Path(value)
        return p if p.is_absolute() else ROOT / p

    @property
    def kb_path(self) -> Path:
        return self.path(self.kb_dir)

    @property
    def index_path(self) -> Path:
        return self.path(self.index_dir)

    @property
    def crm_path(self) -> Path:
        return self.path(self.crm_dir)

    @property
    def traces_path(self) -> Path:
        return self.path(self.traces_dir)

    @property
    def services_kb_path(self) -> Path:
        return self.path(self.services_kb_dir)

    @property
    def services_index_path(self) -> Path:
        return self.path(self.services_index_dir)


@lru_cache
def get_settings() -> Settings:
    return Settings()
