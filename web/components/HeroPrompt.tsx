"use client";

import { useState } from "react";

const SUGGESTIONS = [
  "I want an AI chatbot over our help docs",
  "Automate our incoming email triage",
  "An AI sales assistant that books demos",
  "Audit our existing bot for accuracy",
];

export function HeroPrompt({
  onSubmit,
  busy,
}: {
  onSubmit: (problem: string) => void;
  busy: boolean;
}) {
  const [value, setValue] = useState("");

  function submit() {
    const problem = value.trim();
    if (problem && !busy) onSubmit(problem);
  }

  return (
    <div className="w-full">
      <div className="rounded-card border border-line bg-surface shadow-card p-2 focus-within:border-line-strong transition-colors">
        <textarea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if ((e.metaKey || e.ctrlKey) && e.key === "Enter") submit();
          }}
          rows={3}
          placeholder="Describe the AI problem in your business — e.g. “customers keep asking the same questions and we want a bot over our docs that also captures leads.”"
          className="w-full resize-none bg-transparent px-4 py-3 text-[15px] leading-relaxed text-ink placeholder:text-muted/60 outline-none"
        />
        <div className="flex items-center justify-between gap-3 px-2 pb-1">
          <span className="text-xs text-muted/80 pl-2">
            ⌘/Ctrl + Enter to send · seeded demo, no signup
          </span>
          <button
            onClick={submit}
            disabled={busy || !value.trim()}
            className="inline-flex items-center gap-2 rounded-xl bg-brand px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition-all hover:bg-brand-ink disabled:cursor-not-allowed disabled:opacity-40"
          >
            {busy ? "Scoping…" : "Scope my project"}
            {!busy && <span aria-hidden>→</span>}
          </button>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            onClick={() => {
              setValue(s);
              if (!busy) onSubmit(s);
            }}
            disabled={busy}
            className="rounded-full border border-line bg-soft px-3.5 py-1.5 text-[13px] text-brand-ink transition-colors hover:border-line-strong hover:bg-white disabled:opacity-50"
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}
