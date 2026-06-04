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
    hashing_dim: int = 1024
    openai_embed_model: str = "text-embedding-3-small"
    openai_api_key: str | None = None

    # --- Generation (Day 2+) -------------------------------------------------
    anthropic_api_key: str | None = None

    def path(self, value: str) -> Path:
        p = Path(value)
        return p if p.is_absolute() else ROOT / p

    @property
    def kb_path(self) -> Path:
        return self.path(self.kb_dir)

    @property
    def index_path(self) -> Path:
        return self.path(self.index_dir)


@lru_cache
def get_settings() -> Settings:
    return Settings()
