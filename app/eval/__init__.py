"""Day 3 eval harness: score the agent on a labeled dataset.

Measures what almost no freelancer shows — retrieval hit-rate, answer
correctness (LLM-as-judge against a rubric), refusal correctness, and tool-call
correctness — and rolls it into a report. Runs on any provider; with the
keyless FakeProvider it's CI-safe (plumbing tested without spend).
"""
from __future__ import annotations

from .dataset import EvalCase, load_cases
from .judge import Judge, Verdict
from .runner import EvalReport, format_report, run_eval
from .scorer import CaseScore, score_case

__all__ = [
    "EvalCase",
    "load_cases",
    "Judge",
    "Verdict",
    "EvalReport",
    "format_report",
    "run_eval",
    "CaseScore",
    "score_case",
]
