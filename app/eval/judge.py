"""LLM-as-judge: grade an answer against a rubric.

Provider-agnostic — takes any `LLMProvider`. The judge accumulates its own token
usage so the runner can report judging cost separately from agent cost.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..llm import LLMMessage, LLMProvider, Usage

JUDGE_SYSTEM = (
    "You are a strict QA grader for a customer-support assistant. Given a "
    "question, the assistant's reply, and a rubric, decide whether the reply "
    "meets the rubric. Be objective. Respond with EXACTLY two lines:\n"
    "VERDICT: PASS or FAIL\n"
    "REASON: <one short sentence>"
)


@dataclass
class Verdict:
    passed: bool
    reason: str


def parse_verdict(text: str) -> Verdict:
    m = re.search(r"VERDICT:\s*(PASS|FAIL)", text, re.IGNORECASE)
    passed = bool(m and m.group(1).upper() == "PASS")
    rm = re.search(r"REASON:\s*(.+)", text, re.IGNORECASE | re.DOTALL)
    reason = (rm.group(1).strip() if rm else text.strip())[:200]
    return Verdict(passed, reason)


class Judge:
    def __init__(self, provider: LLMProvider, max_tokens: int = 200) -> None:
        self.provider = provider
        self.max_tokens = max_tokens
        self.usage = Usage()

    def grade(
        self, question: str, answer: str, rubric: str, expect_refusal: bool = False
    ) -> Verdict:
        guidance = (
            "The assistant SHOULD decline or escalate and must NOT fabricate an answer."
            if expect_refusal
            else "The assistant should correctly answer per the rubric."
        )
        user = (
            f"QUESTION:\n{question}\n\n"
            f"ASSISTANT REPLY:\n{answer}\n\n"
            f"RUBRIC (what a correct reply requires):\n{rubric}\n\n"
            f"GUIDANCE: {guidance}\n\nGrade now."
        )
        resp = self.provider.generate(
            system=JUDGE_SYSTEM,
            messages=[LLMMessage(role="user", content=user)],
            tools=None,
            max_tokens=self.max_tokens,
        )
        self.usage = self.usage + resp.usage
        return parse_verdict(resp.text)
