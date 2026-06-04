import type { SolutionSketch } from "@/lib/types";

export function SolutionSketchCard({ solution }: { solution: SolutionSketch }) {
  return (
    <div className="rounded-card border border-line bg-surface shadow-card p-5">
      <h4 className="text-base font-semibold text-ink">How I&apos;d build it</h4>
      <p className="mt-2 text-[14.5px] leading-relaxed text-muted">{solution.summary}</p>

      {solution.architecture_steps.length > 0 && (
        <ol className="mt-4 space-y-2.5">
          {solution.architecture_steps.map((step, i) => (
            <li key={i} className="flex gap-3 text-[14px] text-ink">
              <span className="flex h-6 w-6 flex-none items-center justify-center rounded-full bg-soft text-xs font-semibold text-brand-ink">
                {i + 1}
              </span>
              <span className="pt-0.5">{step}</span>
            </li>
          ))}
        </ol>
      )}

      {solution.stack_notes.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-2">
          {solution.stack_notes.map((note, i) => (
            <span
              key={i}
              className="rounded-full border border-line bg-soft px-3 py-1 text-xs text-brand-ink"
            >
              {note}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
