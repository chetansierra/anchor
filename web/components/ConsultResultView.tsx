import type { ConsultResult } from "@/lib/types";
import { ServiceMatchCard } from "@/components/cards/ServiceMatchCard";
import { SolutionSketchCard } from "@/components/cards/SolutionSketchCard";
import { TimelineCard } from "@/components/cards/TimelineCard";
import { LeadCaptureForm } from "@/components/LeadCaptureForm";
import { NimbusLink } from "@/components/NimbusLink";

// ids must match lib/sections.ts (the right-rail TOC anchors to them)

export function ConsultResultView({
  result,
  problem,
}: {
  result: ConsultResult;
  problem: string;
}) {
  return (
    <div className="space-y-8 animate-fade-up">
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

      {/* Stacked, full-width blocks — each anchored for the right-rail TOC. The
          services group is labelled + numbered; the other cards carry titles. */}
      <section id="sec-services" className="scroll-mt-24">
        <h3 className="mb-2.5 text-xs font-semibold uppercase tracking-wide text-muted">
          Services that fit{result.services.length > 1 ? ` · ${result.services.length}` : ""}
        </h3>
        <div className="space-y-3">
          {result.services.map((s, i) => (
            <ServiceMatchCard key={s.service_id} service={s} index={i + 1} />
          ))}
        </div>
      </section>

      <section id="sec-solution" className="scroll-mt-24">
        <SolutionSketchCard solution={result.solution} />
      </section>

      <section id="sec-timeline" className="scroll-mt-24">
        <TimelineCard phases={result.timeline} />
      </section>

      <section id="sec-contact" className="scroll-mt-24">
        <LeadCaptureForm
          problem={problem}
          serviceIds={result.services.map((s) => s.service_id)}
        />
      </section>

      <section id="sec-example" className="scroll-mt-24">
        <NimbusLink />
      </section>
    </div>
  );
}
