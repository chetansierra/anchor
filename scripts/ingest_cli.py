"""Build (or rebuild) the indexes from the command line.

    python -m scripts.ingest_cli

Builds BOTH corpora:
  - the Nimbus support KB  (data/kb        -> data/index)
  - the services KB         (data/services_kb -> data/services_index)
that power the /chat support demo and the /consult landing-page consultant.
"""
from __future__ import annotations

from app.config import get_settings
from app.ingest import run_ingest


def _report(label: str, kb_path, index_path, stats) -> None:
    print(
        f"[{label}] ingested {kb_path}\n"
        f"  documents : {stats.documents}\n"
        f"  chunks    : {stats.chunks}\n"
        f"  embedder  : {stats.embedder} (dim {stats.dim})\n"
        f"  elapsed   : {stats.elapsed_ms} ms\n"
        f"  index     : {index_path}"
    )


def main() -> None:
    settings = get_settings()

    support = run_ingest(settings)
    _report("support", settings.kb_path, settings.index_path, support)

    services = run_ingest(
        settings,
        kb_path=settings.services_kb_path,
        index_path=settings.services_index_path,
    )
    _report("services", settings.services_kb_path, settings.services_index_path, services)


if __name__ == "__main__":
    main()
