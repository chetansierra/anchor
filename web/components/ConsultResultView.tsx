import type { ConsultResult } from "@/lib/types";
import { ServiceMatchCard } from "@/components/cards/ServiceMatchCard";
import { SolutionSketchCard } from "@/components/cards/SolutionSketchCard";
import { TimelineCard } from "@/components/cards/TimelineCard";
import { LeadCaptureForm } from "@/components/LeadCaptureForm";
import { NimbusLink } from "@/components/NimbusLink";

export function ConsultResultView({
  result,
  problem,
}: {
  result: ConsultResult;
  problem: string;
}) {
  return (
    <div className="space-y-5 animate-fade-up">
      <div>
        <p className="text-[15px] leading-relaxed text-ink">{result.problem_restatement}</p>
        {result.grounded && (
          <p className="mt-1 text-xs text-muted">
            Grounded in {result.citations.length} source
            {result.citations.length === 1 ? "" : "s"} about my services
            {result.model ? ` · ${result.model}` : ""}
          </p>
        )}
      </div>

      <section>
        <h3 className="mb-2.5 text-xs font-semibold uppercase tracking-wide text-muted">
          Services that fit
        </h3>
        <div className="grid gap-3 sm:grid-cols-2">
          {result.services.map((s) => (
            <ServiceMatchCard key={s.service_id} service={s} />
          ))}
        </div>
      </section>

      <div className="grid gap-3 lg:grid-cols-2">
        <SolutionSketchCard solution={result.solution} />
        <TimelineCard phases={result.timeline} />
      </div>

      <LeadCaptureForm
        problem={problem}
        serviceIds={result.services.map((s) => s.service_id)}
      />

      <NimbusLink />
    </div>
  );
}
