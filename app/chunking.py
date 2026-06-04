"""Token-aware chunking.

We target ~`chunk_target_tokens` per chunk with a sliding overlap so retrieval
keeps surrounding context. To stay dependency-free and offline-friendly we
estimate tokens from characters (~4 chars/token); if `tiktoken` is importable we
use it for an exact count instead. Boundaries prefer sentence breaks so we don't
split mid-thought.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable


@dataclass
class Chunk:
    index: int
    text: str
    n_tokens: int


def build_token_counter(chars_per_token: float) -> Callable[[str], int]:
    """Return a function that counts tokens, exact if tiktoken is available."""
    try:
        import tiktoken  # type: ignore

        enc = tiktoken.get_encoding("cl100k_base")
        return lambda s: len(enc.encode(s))
    except Exception:
        return lambda s: max(1, round(len(s) / chars_per_token))


# Split on sentence-ending punctuation followed by whitespace, keeping it simple
# and dependency-free. Newlines are treated as soft sentence boundaries too.
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+|\n{2,}")


def _split_sentences(text: str) -> list[str]:
    parts = [s.strip() for s in _SENTENCE_RE.split(text)]
    return [s for s in parts if s]


def chunk_text(
    text: str,
    *,
    target_tokens: int,
    overlap_tokens: int,
    count_tokens: Callable[[str], int],
) -> list[Chunk]:
    """Greedily pack sentences into ~target_tokens chunks with token overlap."""
    sentences = _split_sentences(text)
    if not sentences:
        return []

    chunks: list[Chunk] = []
    current: list[str] = []
    current_tokens = 0

    def flush() -> None:
        nonlocal current, current_tokens
        if not current:
            return
        body = " ".join(current).strip()
        chunks.append(Chunk(index=len(chunks), text=body, n_tokens=count_tokens(body)))
        # Seed the next chunk with a tail of sentences to create overlap.
        if overlap_tokens > 0:
            tail: list[str] = []
            tail_tokens = 0
            for sent in reversed(current):
                t = count_tokens(sent)
                if tail_tokens + t > overlap_tokens:
                    break
                tail.insert(0, sent)
                tail_tokens += t
            current = tail
            current_tokens = tail_tokens
        else:
            current = []
            current_tokens = 0

    for sentence in sentences:
        t = count_tokens(sentence)
        # A single oversized sentence becomes its own chunk.
        if t >= target_tokens:
            flush()
            chunks.append(
                Chunk(index=len(chunks), text=sentence, n_tokens=t)
            )
            current, current_tokens = [], 0
            continue
        if current_tokens + t > target_tokens and current:
            flush()
        current.append(sentence)
        current_tokens += t

    flush()
    # Re-number after the fact in case overlap seeding shifted things.
    for i, c in enumerate(chunks):
        c.index = i
    return chunks
