"""Load the seeded knowledge base from markdown files.

Each `*.md` under the KB dir is one document. The title is taken from the first
H1 (`# ...`) if present, otherwise the filename. The doc_id is the file stem.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Document:
    doc_id: str
    title: str
    source: str
    text: str


_H1_RE = re.compile(r"^\s*#\s+(.+?)\s*$", re.MULTILINE)


def _title_from(text: str, fallback: str) -> str:
    m = _H1_RE.search(text)
    return m.group(1).strip() if m else fallback


def load_documents(kb_dir: Path) -> list[Document]:
    kb_dir = Path(kb_dir)
    if not kb_dir.exists():
        raise FileNotFoundError(f"KB directory not found: {kb_dir}")

    docs: list[Document] = []
    for path in sorted(kb_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            continue
        stem = path.stem
        docs.append(
            Document(
                doc_id=stem,
                title=_title_from(text, fallback=stem.replace("-", " ").title()),
                source=path.name,
                text=text,
            )
        )
    return docs
