"""Run the eval harness and write a report.

    python -m scripts.eval_cli

Uses the configured provider (set ANTHROPIC_API_KEY for real LLM-as-judge
numbers; with no key it runs on the keyless FakeProvider for a plumbing check).
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict

from app.agent import Agent
from app.config import get_settings
from app.eval import Judge, format_report, load_cases, run_eval
from app.retrieval import Retriever
from app.vectorstore import LocalVectorStore


def main() -> int:
    settings = get_settings()
    if not LocalVectorStore.exists(settings.index_path):
        print("No index found. Run `make ingest` first.")
        return 1

    retriever = Retriever.load(settings)
    agent = Agent.build(retriever, settings)
    judge = Judge(agent.provider)
    cases = load_cases(settings.path("data/eval/dataset.jsonl"))

    # Optional: pass case ids as args to run a subset (cheap re-check of fixes).
    only = set(sys.argv[1:])
    if only:
        cases = [c for c in cases if c.id in only]

    print(
        f"Running eval: {len(cases)} cases on "
        f"{agent.provider.name}/{agent.provider.model} (judge: same) ...\n"
    )
    report = run_eval(agent, judge, cases)
    print(format_report(report))

    out = settings.path("data/eval/report.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(asdict(report), indent=2))
    print(f"\nReport written to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
