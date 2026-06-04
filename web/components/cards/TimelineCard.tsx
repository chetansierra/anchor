import type { TimelinePhase } from "@/lib/types";

export function TimelineCard({ phases }: { phases: TimelinePhase[] }) {
  if (!phases.length) return null;
  return (
    <div className="rounded-card border border-line bg-surface shadow-card p-5">
      <h4 className="text-base font-semibold text-ink">Rough timeline</h4>
      <ol className="mt-4">
        {phases.map((phase, i) => (
          <li key={i} className="relative flex gap-4 pb-5 last:pb-0">
            {/* connector line */}
            {i < phases.length - 1 && (
              <span className="absolute left-[7px] top-4 h-full w-px bg-line" aria-hidden />
            )}
            <span className="mt-1.5 h-3.5 w-3.5 flex-none rounded-full border-2 border-brand bg-surface" />
            <div className="min-w-0">
              <div className="flex flex-wrap items-baseline gap-x-2">
                <span className="text-[14.5px] font-medium text-ink">{phase.name}</span>
                <span className="text-xs font-medium text-brand-ink">· {phase.duration}</span>
              </div>
              {phase.deliverable && (
                <p className="mt-0.5 text-[13.5px] text-muted">{phase.deliverable}</p>
              )}
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
