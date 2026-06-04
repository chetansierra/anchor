"""Score one agent run against its labeled case.

Each category has a different primary check:
  - answerable   -> answer correctness (LLM-as-judge) + retrieval hit
  - out_of_scope -> refusal correctness (hard-escalation, or judge confirms it
                    declined without fabricating)
  - action       -> the right tool was called (+ retrieval hit if a source is set)
"""
from __future__ import annotations

from dataclasses import dataclass

from ..agent import AgentResult
from .dataset import EvalCase
from .judge import Judge


@dataclass
class CaseScore:
    id: str
    category: str
    primary_pass: bool
    retrieval_hit: bool | None
    detail: str


def score_case(case: EvalCase, result: AgentResult, judge: Judge) -> CaseScore:
    docs = [r["doc_id"] for r in result.retrieved]
    hit = case.expected_source in docs if case.expected_source else None

    if case.category == "answerable":
        v = judge.grade(case.question, result.answer, case.rubric)
        return CaseScore(case.id, case.category, v.passed, hit, "ok" if v.passed else v.reason)

    if case.category == "out_of_scope":
        if result.escalated:  # hard guardrail fired — definitionally a refusal
            return CaseScore(case.id, case.category, True, None, "escalated (guardrail)")
        v = judge.grade(case.question, result.answer, case.rubric, expect_refusal=True)
        return CaseScore(
            case.id, case.category, v.passed, None, "declined" if v.passed else v.reason
        )

    if case.category == "action":
        names = [t.name for t in result.tool_calls]
        ok = case.expected_tool in names if case.expected_tool else bool(names)
        detail = "called " + ",".join(names) if ok else f"expected {case.expected_tool}, got {names or 'none'}"
        return CaseScore(case.id, case.category, ok, hit, detail)

    return CaseScore(case.id, case.category, False, None, f"unknown category {case.category}")
