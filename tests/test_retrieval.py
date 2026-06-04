"""Day 1 regression test: retrieval returns the right source for known queries.

Uses the deterministic HashingEmbedder so the test is hermetic (no model
download, no API key, no network) and runs in CI on every change.
"""
from __future__ import annotations

from app.config import Settings
from app.embeddings import HashingEmbedder
from app.ingest import run_ingest
from app.retrieval import Retriever

EXPECTATIONS = [
    ("How do I reset my password?", "reset-password"),
    ("Can I get a refund after I cancel my plan?", "refund-policy"),
    ("Do you support SAML single sign-on?", "sso-saml"),
    ("What are the API rate limits?", "rate-limits"),
    ("How do I export all of my data?", "data-export"),
]


def _settings(tmp_path) -> Settings:
    # Real KB (default kb_dir), throwaway index dir, deterministic embedder.
    return Settings(index_dir=str(tmp_path / "index"), embedder="hashing")


def test_ingest_builds_index(tmp_path):
    settings = _settings(tmp_path)
    stats = run_ingest(settings, embedder=HashingEmbedder(settings.hashing_dim))
    assert stats.documents >= 15, "expected a seeded KB of at least 15 docs"
    assert stats.chunks >= stats.documents


def test_top_k_contains_expected_source(tmp_path):
    settings = _settings(tmp_path)
    run_ingest(settings, embedder=HashingEmbedder(settings.hashing_dim))
    retriever = Retriever.load(settings, embedder=HashingEmbedder(settings.hashing_dim))

    misses = []
    for question, expected in EXPECTATIONS:
        hits, _ = retriever.search(question, settings.top_k)
        if expected not in {h.record.doc_id for h in hits}:
            misses.append((question, expected, [h.record.doc_id for h in hits]))

    assert not misses, f"retrieval missed expected sources: {misses}"
