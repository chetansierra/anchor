import type { Proof } from "@/lib/types";
import { API_BASE } from "@/lib/api";

export function ProofCard({ proof }: { proof: Proof }) {
  const href = proof.case_study_url?.startsWith("http")
    ? proof.case_study_url
    : `${API_BASE}${proof.case_study_url || "/#proof"}`;
  return (
    <div className="rounded-card border border-brand/20 bg-soft/60 shadow-card p-5">
      <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-brand-ink">
        <span className="h-1.5 w-1.5 rounded-full bg-brand-soft" />
        Proof it works
      </div>
      <p className="mt-2 text-lg font-semibold text-ink">{proof.headline}</p>
      {proof.detail && (
        <p className="mt-1.5 text-[14px] leading-relaxed text-muted">{proof.detail}</p>
      )}
      <a
        href={href}
        target="_blank"
        rel="noreferrer"
        className="mt-3 inline-flex items-center gap-1.5 text-sm font-semibold text-brand hover:text-brand-ink"
      >
        See the live case study <span aria-hidden>→</span>
      </a>
    </div>
  );
}
