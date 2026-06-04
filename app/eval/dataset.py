"""Load the labeled eval dataset (one JSON object per line)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class EvalCase:
    id: str
    category: str  # answerable | out_of_scope | action
    question: str
    expected_source: str | None
    expect_refusal: bool
    expected_tool: str | None
    rubric: str


def load_cases(path: Path) -> list[EvalCase]:
    cases: list[EvalCase] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        d = json.loads(line)
        cases.append(
            EvalCase(
                id=d["id"],
                category=d["category"],
                question=d["question"],
                expected_source=d.get("expected_source"),
                expect_refusal=d.get("expect_refusal", False),
                expected_tool=d.get("expected_tool"),
                rubric=d.get("rubric", ""),
            )
        )
    return cases
