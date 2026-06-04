"use client";

import { useCallback, useState } from "react";
import { streamConsult } from "@/lib/api";
import type { ConsultResult, Stage, StageFrame } from "@/lib/types";
import { HeroPrompt } from "@/components/HeroPrompt";
import { ThinkingStepper } from "@/components/ThinkingStepper";
import { ConsultResultView } from "@/components/ConsultResultView";

type Phase = "idle" | "streaming" | "done" | "error";

function applyStage(prev: Stage[], frame: StageFrame): Stage[] {
  if (frame.status === "start" && frame.label) {
    const closed = prev.map((s) =>
      s.status === "active" ? { ...s, status: "done" as const } : s,
    );
    return [...closed, { step: frame.step, label: frame.label, status: "active" }];
  }
  // a "done" frame: close the matching step and attach any retrieval count
  return prev.map((s) =>
    s.step === frame.step
      ? { ...s, status: "done" as const, docs: frame.meta?.docs ?? s.docs }
      : s,
  );
}

export default function Home() {
  const [phase, setPhase] = useState<Phase>("idle");
  const [problem, setProblem] = useState("");
  const [stages, setStages] = useState<Stage[]>([]);
  const [result, setResult] = useState<ConsultResult | null>(null);
  const [error, setError] = useState("");

  const start = useCallback((p: string) => {
    setPhase("streaming");
    setProblem(p);
    setStages([]);
    setResult(null);
    setError("");
    streamConsult(p, {
      onStage: (frame) => setStages((prev) => applyStage(prev, frame)),
      onResult: (r) => {
        setResult(r);
        setStages((prev) => prev.map((s) => ({ ...s, status: "done" as const })));
        setPhase("done");
      },
      onError: (msg) => {
        setError(msg);
        setPhase("error");
      },
      onDone: () => setPhase((cur) => (cur === "streaming" ? "done" : cur)),
    });
  }, []);

  const busy = phase === "streaming";

  return (
    <main className="min-h-screen">
      <section className="hero-wash">
        <div className="mx-auto max-w-3xl px-5 pt-16 pb-8 sm:pt-24">
          <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-line bg-white/70 px-3 py-1 text-xs font-medium text-brand-ink">
            <span className="h-1.5 w-1.5 animate-pulse-dot rounded-full bg-brand-soft" />
            Production-grade AI agents — evaluated &amp; observable
          </div>
          <h1 className="text-4xl font-semibold leading-tight tracking-tight text-ink sm:text-5xl">
            We can solve any AI problem in your business.{" "}
            <span className="text-brand">Describe yours.</span>
          </h1>
          <p className="mt-4 max-w-2xl text-[16px] leading-relaxed text-muted">
            Tell the agent what you need. Watch it scope your problem live — then read its
            proposed services, approach, timeline, and the proof it works. The demo scoping your
            project is itself an example of the work.
          </p>
          <div className="mt-7">
            <HeroPrompt onSubmit={start} busy={busy} />
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-3xl px-5 pb-24">
        {(busy || stages.length > 0) && (
          <div className="mb-5">
            <ThinkingStepper stages={stages} />
          </div>
        )}

        {phase === "error" && (
          <div className="rounded-card border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            {error}{" "}
            <button onClick={() => start(problem)} className="font-semibold underline">
              try again
            </button>
          </div>
        )}

        {result && <ConsultResultView result={result} problem={problem} />}
      </section>
    </main>
  );
}
