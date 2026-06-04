"""Day 1 acceptance check + artifact.

Runs five hand-picked questions against the index and prints the top-k chunks for
each, plus a PASS/FAIL on whether the expected source document shows up. Builds
the index first if it's missing.

    python -m scripts.retrieve_cli
"""
from __future__ import annotations

import sys

from app.config import get_settings
from app.ingest import run_ingest
from app.retrieval import Retriever
from app.vectorstore import LocalVectorStore

# (question, expected source doc_id that *should* appear in the top-k)
HAND_PICKED: list[tuple[str, str]] = [
    ("How do I reset my password?", "reset-password"),
    ("Can I get a refund after I cancel my plan?", "refund-policy"),
    ("Do you support SAML single sign-on?", "sso-saml"),
    ("What are the API rate limits?", "rate-limits"),
    ("How do I export all of my data?", "data-export"),
]


def main() -> int:
    settings = get_settings()
    if not LocalVectorStore.exists(settings.index_path):
        print("No index found — building it first...\n")
        run_ingest(settings)

    retriever = Retriever.load(settings)
    print(f"Embedder: {retriever.embedder.name}  |  chunks: {retriever.store.count}\n")
    print("=" * 78)

    passed = 0
    for question, expected in HAND_PICKED:
        hits, latency_ms = retriever.search(question, settings.top_k)
        hit_docs = [h.record.doc_id for h in hits]
        ok = expected in hit_docs
        passed += ok
        flag = "PASS" if ok else "FAIL"
        print(f"\n[{flag}] Q: {question}")
        print(f"       expected source: {expected}   ({latency_ms} ms)")
        for rank, h in enumerate(hits, 1):
            marker = " <-- expected" if h.record.doc_id == expected else ""
            preview = h.record.text.replace("\n", " ")[:90]
            print(f"   {rank}. {h.score:.3f}  {h.record.source:<26} {preview}…{marker}")

    print("\n" + "=" * 78)
    print(f"Acceptance: {passed}/{len(HAND_PICKED)} questions returned the right source.")
    return 0 if passed == len(HAND_PICKED) else 1


if __name__ == "__main__":
    sys.exit(main())
