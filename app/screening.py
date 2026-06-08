"""Compliance pre-screen for the consultant's free-form input.

Keeps the public demo clean: obviously out-of-scope or harmful requests are
declined BEFORE any model call (so they cost nothing and never get a proposal).

Deliberately HIGH-PRECISION and phrase-based, not single keywords, to avoid
false-positives on legitimate business language — e.g. "support cheat sheet",
"AI to grade exams for our edtech product", or "kill the latency" must all pass.
A second, model-side check (the emit_consult `in_scope` flag) handles the subtler
cases this can't.
"""
from __future__ import annotations

DECLINE_MESSAGE = (
    "I can only help scope legitimate AI projects for a business or organization. "
    "Tell me a real problem you'd like to solve — like a support chatbot over your "
    "docs, automating a repetitive workflow, or capturing leads — and I'll map out "
    "an approach."
)

# Unambiguous, multi-word signals of an out-of-scope or harmful request.
_BLOCK_PHRASES: tuple[str, ...] = (
    # academic dishonesty
    "cheat in", "cheat on", "cheat at", "cheat during", "cheating in",
    "cheating on", "cheating at", "help me cheat", "do my homework",
    "do my assignment", "write my essay", "write my assignment", "pass my exam",
    "pass the exam", "pass an exam", "during the exam", "during an exam",
    "during the test", "during a test",
    # hacking / unauthorized access
    "hack into", "hack someone", "hack my school", "hack a", "steal password",
    "steal credentials", "steal data from", "bypass login", "ddos",
    # violence / weapons
    "make a bomb", "build a bomb", "how to kill", "harm someone",
    # fraud / deception
    "fake review", "fake reviews", "launder money", "money laundering",
    "fake id", "forge a",
    # sexual abuse material
    "child porn", "child sexual", "csam",
    # self-harm
    "kill myself", "commit suicide", "end my life",
)


def is_blocked(problem: str) -> bool:
    """Cheap, high-precision pre-screen. True => decline before any model call."""
    text = " ".join((problem or "").lower().split())
    if len(text) < 6:  # empty / too short to be a genuine request
        return True
    return any(phrase in text for phrase in _BLOCK_PHRASES)
