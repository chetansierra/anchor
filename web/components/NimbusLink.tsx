import { API_BASE } from "@/lib/api";

export function NimbusLink() {
  return (
    <div className="rounded-card border border-line bg-surface shadow-card p-5">
      <h4 className="text-base font-semibold text-ink">See a deployed example</h4>
      <p className="mt-1 text-[14px] leading-relaxed text-muted">
        This consultant runs the same engine I ship to clients — the page scoping your
        project is itself an example of the work. The Nimbus demo is a live support agent
        built on the same stack.
      </p>
      <div className="mt-3">
        <a
          href={`${API_BASE}/`}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1.5 rounded-xl border border-line bg-soft px-4 py-2 text-sm font-semibold text-brand-ink transition-colors hover:bg-white"
        >
          Open the Nimbus demo <span aria-hidden>↗</span>
        </a>
      </div>
    </div>
  );
}
