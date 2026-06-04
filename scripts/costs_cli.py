"""Daily cost rollup — the answer to "what will this cost me to run?".

Reads the recorded traces and prints a per-day table (runs, tokens, escalations,
$ cost) plus totals and a projected monthly run-rate from the busiest day. No API
calls — pure local accounting over data/traces/traces.jsonl.

    python -m scripts.costs_cli
"""
from __future__ import annotations

import sys

from app.config import get_settings
from app.traces import TraceStore


def main() -> int:
    store = TraceStore(get_settings().traces_path)
    ov = store.overview()

    if ov.total_runs == 0:
        print("No traces yet. Run some /chat requests (or `make run`) first.")
        return 0

    print(f"\nObservability rollup  ·  {store.path}")
    print("=" * 72)
    print(f"{'Date':<12}{'Runs':>6}{'In tok':>10}{'Out tok':>10}{'Escal.':>8}{'Cost':>12}")
    print("-" * 72)
    for d in ov.daily:
        print(
            f"{d['date']:<12}{d['runs']:>6}{d['input_tokens']:>10}"
            f"{d['output_tokens']:>10}{d['escalated']:>8}{'$' + format(d['cost_usd'], '.4f'):>12}"
        )
    print("-" * 72)
    print(
        f"{'TOTAL':<12}{ov.total_runs:>6}{ov.total_input_tokens:>10}"
        f"{ov.total_output_tokens:>10}{ov.outcomes.get('escalated', 0):>8}"
        f"{'$' + format(ov.total_cost_usd, '.4f'):>12}"
    )
    print("=" * 72)
    print(f"Avg cost / conversation : ${ov.avg_cost_per_conversation:.4f}")
    print(f"Avg latency             : {ov.avg_latency_ms:.0f} ms")
    print(f"Escalation rate         : {ov.escalation_rate * 100:.1f}%")

    busiest = max(ov.daily, key=lambda d: d["runs"])
    print(
        f"\nRun-rate (busiest day {busiest['date']}: {busiest['runs']} runs):"
        f" ~${busiest['cost_usd'] * 30:.2f}/mo at that volume."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
