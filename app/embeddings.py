"""Embedding backends behind one interface.

The whole point of the freelance positioning is "swap providers without rewiring
the app", so retrieval depends only on the `Embedder` protocol below. Three
backends ship today:

  - HashingEmbedder  : zero-dependency, offline, deterministic. Always available
                       so the pipeline runs with no model download and no key.
  - FastEmbedEmbedder: real local sentence embeddings via ONNX (no API key).
  - OpenAIEmbedder   : hosted embeddings (needs OPENAI_API_KEY).

`build_embedder(settings)` resolves the configured choice, with "auto" picking
the best available option.
"""
from __future__ import annotations

import hashlib
import re
from typing import Protocol, runtime_checkable

import numpy as np

from .config import Settings


@runtime_checkable
class Embedder(Protocol):
    name: str
    dim: int

    def embed_documents(self, texts: list[str]) -> np.ndarray: ...
    def embed_query(self, text: str) -> np.ndarray: ...


def _l2_normalize(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=-1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms


class HashingEmbedder:
    """Signed feature hashing over words + character 3-grams.

    Not semantic, but for a small KB where questions share vocabulary with the
    docs it gives solid top-k retrieval — and it has zero dependencies, so Day 1
    always works. It also makes a nice eval baseline ("watch quality jump when we
    swap in a real model").
    """

    name = "hashing"

    def __init__(self, dim: int = 1024) -> None:
        self.dim = dim

    def _tokens(self, text: str) -> list[str]:
        words = re.findall(r"[a-z0-9]+", text.lower())
        grams: list[str] = []
        for w in words:
            grams.append(w)
            padded = f"#{w}#"
            for i in range(len(padded) - 2):
                grams.append(padded[i : i + 3])
        return grams

    def _embed_one(self, text: str) -> np.ndarray:
        vec = np.zeros(self.dim, dtype=np.float32)
        for tok in self._tokens(text):
            h = int.from_bytes(hashlib.md5(tok.encode()).digest()[:8], "big")
            idx = h % self.dim
            sign = 1.0 if (h >> 7) & 1 else -1.0
            vec[idx] += sign
        return vec

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        mat = np.vstack([self._embed_one(t) for t in texts]) if texts else np.zeros((0, self.dim), np.float32)
        return _l2_normalize(mat)

    def embed_query(self, text: str) -> np.ndarray:
        return _l2_normalize(self._embed_one(text)[None, :])[0]


class FastEmbedEmbedder:
    """Local ONNX sentence embeddings via the `fastembed` package."""

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5", query_prefix: str = "") -> None:
        from fastembed import TextEmbedding  # type: ignore

        self.name = f"fastembed:{model_name}"
        self._query_prefix = query_prefix
        self._model = TextEmbedding(model_name=model_name)
        # Probe dimensionality once.
        self.dim = int(next(iter(self._model.embed(["dimension probe"]))).shape[0])

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), np.float32)
        mat = np.array(list(self._model.embed(texts)), dtype=np.float32)
        return _l2_normalize(mat)

    def embed_query(self, text: str) -> np.ndarray:
        # BGE-v1.5 retrieval benefits from a short instruction prefix on the
        # query side only; passages are embedded as-is.
        query = f"{self._query_prefix}{text}" if self._query_prefix else text
        vec = np.array(next(iter(self._model.embed([query]))), dtype=np.float32)
        return _l2_normalize(vec[None, :])[0]


class OpenAIEmbedder:
    """Hosted embeddings via the OpenAI API (needs OPENAI_API_KEY)."""

    def __init__(self, model_name: str, api_key: str) -> None:
        from openai import OpenAI  # type: ignore

        self.name = f"openai:{model_name}"
        self._model_name = model_name
        self._client = OpenAI(api_key=api_key)
        self.dim = len(self._embed(["dimension probe"])[0])

    def _embed(self, texts: list[str]) -> list[list[float]]:
        resp = self._client.embeddings.create(model=self._model_name, input=texts)
        return [d.embedding for d in resp.data]

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), np.float32)
        return _l2_normalize(np.array(self._embed(texts), dtype=np.float32))

    def embed_query(self, text: str) -> np.ndarray:
        return _l2_normalize(np.array(self._embed([text]), dtype=np.float32))[0]


def build_embedder(settings: Settings) -> Embedder:
    """Resolve the configured embedder, honoring 'auto' fallback order."""
    choice = settings.embedder.lower()

    def make_fastembed() -> Embedder:
        return FastEmbedEmbedder(settings.fastembed_model, settings.fastembed_query_prefix)

    def make_openai() -> Embedder:
        if not settings.openai_api_key:
            raise RuntimeError("EMBEDDER=openai but OPENAI_API_KEY is not set.")
        return OpenAIEmbedder(settings.openai_embed_model, settings.openai_api_key)

    def make_hashing() -> Embedder:
        return HashingEmbedder(settings.hashing_dim)

    if choice == "fastembed":
        return make_fastembed()
    if choice == "openai":
        return make_openai()
    if choice == "hashing":
        return make_hashing()

    # auto: best available, never failing.
    try:
        return make_fastembed()
    except Exception:
        pass
    if settings.openai_api_key:
        try:
            return make_openai()
        except Exception:
            pass
    return make_hashing()
