"""Vector store behind one interface.

For the demo we ship `LocalVectorStore`: a numpy matrix of L2-normalized vectors
plus a parallel list of chunk metadata, persisted to disk. Cosine similarity is
then a single matrix-vector dot product — fast and transparent for a KB of this
size, and easy to reason about while learning. The `VectorStore` protocol lets us
drop in pgvector or Qdrant later without touching the rest of the app.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol

import numpy as np


@dataclass
class ChunkRecord:
    id: str
    doc_id: str
    title: str
    source: str
    chunk_index: int
    text: str


@dataclass
class SearchHit:
    record: ChunkRecord
    score: float


class VectorStore(Protocol):
    def upsert(self, vectors: np.ndarray, records: list[ChunkRecord]) -> None: ...
    def search(self, query_vector: np.ndarray, k: int) -> list[SearchHit]: ...
    def save(self) -> None: ...
    @property
    def count(self) -> int: ...


class LocalVectorStore:
    """numpy-backed cosine store persisted as vectors.npy + records.json."""

    VECTORS_FILE = "vectors.npy"
    RECORDS_FILE = "records.json"
    MANIFEST_FILE = "manifest.json"

    def __init__(self, index_dir: Path, embedder_name: str, dim: int) -> None:
        self.index_dir = Path(index_dir)
        self.embedder_name = embedder_name
        self.dim = dim
        self._vectors = np.zeros((0, dim), dtype=np.float32)
        self._records: list[ChunkRecord] = []

    # --- mutation ------------------------------------------------------------
    def upsert(self, vectors: np.ndarray, records: list[ChunkRecord]) -> None:
        if vectors.shape[0] != len(records):
            raise ValueError("vectors and records length mismatch")
        if vectors.shape[0] == 0:
            return
        if vectors.shape[1] != self.dim:
            raise ValueError(f"expected dim {self.dim}, got {vectors.shape[1]}")
        self._vectors = np.vstack([self._vectors, vectors.astype(np.float32)])
        self._records.extend(records)

    def reset(self) -> None:
        self._vectors = np.zeros((0, self.dim), dtype=np.float32)
        self._records = []

    # --- query ---------------------------------------------------------------
    def search(self, query_vector: np.ndarray, k: int) -> list[SearchHit]:
        if self.count == 0:
            return []
        scores = self._vectors @ query_vector.astype(np.float32)
        k = min(k, self.count)
        # argpartition for the top-k, then sort just those.
        top_idx = np.argpartition(-scores, k - 1)[:k]
        top_idx = top_idx[np.argsort(-scores[top_idx])]
        return [SearchHit(record=self._records[i], score=float(scores[i])) for i in top_idx]

    @property
    def count(self) -> int:
        return len(self._records)

    @property
    def n_documents(self) -> int:
        return len({r.doc_id for r in self._records})

    # --- persistence ---------------------------------------------------------
    def save(self) -> None:
        self.index_dir.mkdir(parents=True, exist_ok=True)
        np.save(self.index_dir / self.VECTORS_FILE, self._vectors)
        (self.index_dir / self.RECORDS_FILE).write_text(
            json.dumps([asdict(r) for r in self._records], ensure_ascii=False, indent=2)
        )
        (self.index_dir / self.MANIFEST_FILE).write_text(
            json.dumps(
                {"embedder": self.embedder_name, "dim": self.dim, "count": self.count},
                indent=2,
            )
        )

    @classmethod
    def load(cls, index_dir: Path) -> "LocalVectorStore":
        index_dir = Path(index_dir)
        manifest = json.loads((index_dir / cls.MANIFEST_FILE).read_text())
        store = cls(index_dir, manifest["embedder"], int(manifest["dim"]))
        store._vectors = np.load(index_dir / cls.VECTORS_FILE)
        records = json.loads((index_dir / cls.RECORDS_FILE).read_text())
        store._records = [ChunkRecord(**r) for r in records]
        return store

    @classmethod
    def exists(cls, index_dir: Path) -> bool:
        index_dir = Path(index_dir)
        return all(
            (index_dir / f).exists()
            for f in (cls.VECTORS_FILE, cls.RECORDS_FILE, cls.MANIFEST_FILE)
        )
