"use client";

import { useState } from "react";
import { submitLead } from "@/lib/api";

export function LeadCaptureForm({
  problem,
  serviceIds,
}: {
  problem: string;
  serviceIds: string[];
}) {
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [status, setStatus] = useState<"idle" | "sending" | "done" | "error">("idle");
  const [error, setError] = useState("");

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!email.trim() || status === "sending") return;
    setStatus("sending");
    setError("");
    try {
      await submitLead({ email: email.trim(), name: name.trim() || undefined, problem, services: serviceIds });
      setStatus("done");
    } catch (err) {
      setError((err as Error).message);
      setStatus("error");
    }
  }

  if (status === "done") {
    return (
      <div className="rounded-card border border-brand/30 bg-soft p-5 text-center animate-fade-up">
        <p className="text-base font-semibold text-brand-ink">Lead captured ✅</p>
        <p className="mt-1 text-sm text-muted">
          Thanks — I&apos;ll follow up about scoping this for you. (In the demo this wrote a row
          to the mock CRM.)
        </p>
      </div>
    );
  }

  return (
    <form
      onSubmit={onSubmit}
      className="rounded-card border border-line bg-surface shadow-card p-5"
    >
      <h4 className="text-base font-semibold text-ink">Want me to scope this for real?</h4>
      <p className="mt-1 text-[14px] text-muted">
        Leave your email and I&apos;ll follow up with a fixed scope and price.
      </p>
      <div className="mt-3 flex flex-col gap-2 sm:flex-row">
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Name (optional)"
          className="w-full rounded-xl border border-line bg-white px-3.5 py-2.5 text-sm text-ink outline-none focus:border-line-strong sm:w-1/3"
        />
        <input
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="you@company.com"
          className="w-full rounded-xl border border-line bg-white px-3.5 py-2.5 text-sm text-ink outline-none focus:border-line-strong"
        />
        <button
          type="submit"
          disabled={status === "sending" || !email.trim()}
          className="whitespace-nowrap rounded-xl bg-brand px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-brand-ink disabled:opacity-40"
        >
          {status === "sending" ? "Sending…" : "Book a call"}
        </button>
      </div>
      {status === "error" && <p className="mt-2 text-sm text-red-600">{error}</p>}
    </form>
  );
}
