import type { Stage } from "@/lib/types";

function Spinner() {
  return (
    <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-brand/30 border-t-brand" />
  );
}

function Check() {
  return (
    <svg viewBox="0 0 20 20" className="h-4 w-4 text-brand" fill="currentColor" aria-hidden>
      <path
        fillRule="evenodd"
        d="M16.7 5.3a1 1 0 010 1.4l-7.5 7.5a1 1 0 01-1.4 0L3.3 9.7a1 1 0 011.4-1.4l3.3 3.3 6.8-6.8a1 1 0 011.9.5z"
        clipRule="evenodd"
      />
    </svg>
  );
}

export function ThinkingStepper({ stages }: { stages: Stage[] }) {
  if (!stages.length) return null;
  return (
    <div className="rounded-card border border-line bg-surface shadow-card p-4 animate-fade-up">
      <div className="mb-3 flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted">
        <span className="h-1.5 w-1.5 animate-pulse-dot rounded-full bg-brand-soft" />
        The agent is working
      </div>
      <ul className="space-y-2.5">
        {stages.map((s) => (
          <li key={s.step} className="flex items-center gap-3 text-[15px]">
            <span className="flex h-5 w-5 items-center justify-center">
              {s.status === "done" ? <Check /> : <Spinner />}
            </span>
            <span className={s.status === "done" ? "text-ink" : "text-muted"}>
              {s.label}
            </span>
            {typeof s.docs === "number" && (
              <span className="ml-auto rounded-full bg-soft px-2 py-0.5 text-xs text-brand-ink">
                {s.docs} source{s.docs === 1 ? "" : "s"}
              </span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
