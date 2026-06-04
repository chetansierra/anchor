"""Build (or rebuild) the KB index from the command line.

    python -m scripts.ingest_cli
"""
from __future__ import annotations

from app.config import get_settings
from app.ingest import run_ingest


def main() -> None:
    settings = get_settings()
    print(f"Ingesting KB from {settings.kb_path} ...")
    stats = run_ingest(settings)
    print(
        f"  documents : {stats.documents}\n"
        f"  chunks    : {stats.chunks}\n"
        f"  embedder  : {stats.embedder} (dim {stats.dim})\n"
        f"  elapsed   : {stats.elapsed_ms} ms\n"
        f"  index     : {settings.index_path}"
    )


if __name__ == "__main__":
    main()
