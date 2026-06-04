"""Run the agent over the dataset, aggregate scores, and format a report."""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from ..agent import Agent
from ..llm.pricing import estimate_cost_usd
from .dataset import EvalCase
from .judge import Judge
from .scorer import score_case


@dataclass
class EvalReport:
    provider: str
    model: str
    total: int
    overall_accuracy: float
    retrieval_hit_rate: float | None
    by_category: dict
    agent_cost_usd: float
    judge_cost_usd: float
    elapsed_s: float
    failures: list[dict] = field(default_factory=list)


def run_eval(agent: Agent, judge: Judge, cases: list[EvalCase]) -> EvalReport:
    started = time.perf_counter()
    passed = agent_cost = 0
    hit_num = hit_den = 0
    by_cat: dict[str, list[int]] = {}
    failures: list[dict] = []

    for case in cases:
        result = agent.run(case.question)
        agent_cost += result.cost_usd
        s = score_case(case, result, judge)

        bucket = by_cat.setdefault(case.category, [0, 0])
        bucket[1] += 1
        bucket[0] += int(s.primary_pass)
        passed += int(s.primary_pass)
        if s.retrieval_hit is not None:
            hit_den += 1
            hit_num += int(s.retrieval_hit)
        if not s.primary_pass:
            failures.append(
                {
                    "id": case.id,
                    "category": case.category,
                    "question": case.question,
                    "detail": s.detail,
                    "answer": result.answer[:200],
                }
            )

    total = len(cases)
    by_category = {
        k: {"pass": v[0], "total": v[1], "accuracy": round(v[0] / v[1], 3)}
        for k, v in by_cat.items()
    }
    return EvalReport(
        provider=agent.provider.name,
        model=agent.provider.model,
        total=total,
        overall_accuracy=round(passed / total, 3) if total else 0.0,
        retrieval_hit_rate=round(hit_num / hit_den, 3) if hit_den else None,
        by_category=by_category,
        agent_cost_usd=round(agent_cost, 4),
        judge_cost_usd=round(estimate_cost_usd(judge.provider.model, judge.usage), 4),
        elapsed_s=round(time.perf_counter() - started, 1),
        failures=failures,
    )


def format_report(r: EvalReport) -> str:
    lines = [
        "=" * 70,
        f"ANCHOR EVAL — {r.provider} / {r.model}",
        "=" * 70,
        f"Overall accuracy : {r.overall_accuracy * 100:5.1f}%   ({r.total} cases)",
    ]
    if r.retrieval_hit_rate is not None:
        lines.append(f"Retrieval hit@k  : {r.retrieval_hit_rate * 100:5.1f}%")
    lines.append("By category:")
    for name, m in sorted(r.by_category.items()):
        lines.append(f"  {name:14} {m['accuracy'] * 100:5.1f}%   ({m['pass']}/{m['total']})")
    lines.append(
        f"Cost: agent ${r.agent_cost_usd} + judge ${r.judge_cost_usd}"
        f"   |   {r.elapsed_s}s"
    )
    if r.failures:
        lines.append(f"\nFailures ({len(r.failures)}):")
        for f in r.failures:
            lines.append(f"  [{f['category']:12}] {f['id']}: {f['detail']}")
    lines.append("=" * 70)
    return "\n".join(lines)
