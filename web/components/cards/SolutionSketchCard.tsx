import type { SolutionSketch } from "@/lib/types";

export function SolutionSketchCard({ solution }: { solution: SolutionSketch }) {
  return (
    <div className="rounded-card border border-line bg-surface shadow-card p-5">
      <h4 className="text-base font-semibold text-ink">What you&apos;ll get</h4>
      {solution.summary && (
        <p className="mt-1.5 text-[14px] leading-relaxed text-muted">{solution.summary}</p>
      )}

      {solution.outcomes.length > 0 && (
        <ul className="mt-3 grid gap-2 sm:grid-cols-2">
          {solution.outcomes.map((outcome, i) => (
            <li key={i} className="flex gap-2 text-[14px] text-ink">
              <span className="mt-[7px] h-1.5 w-1.5 flex-none rounded-full bg-brand-soft" />
              {outcome}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
