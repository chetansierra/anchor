import type { ConsultResult } from "@/lib/types";

export const sampleResult: ConsultResult = {
  problem_restatement: "You want a chatbot over your help docs that also captures leads.",
  services: [
    {
      service_id: "rag_support_agent",
      name: "Website AI support agent",
      fit_reason: "Answers from your docs with citations.",
      whats_included: ["Ingest your docs", "Grounded answers"],
      price_band: { label: "Fixed scope", low_usd: 300, high_usd: 800 },
      confidence: 0.8,
    },
    {
      service_id: "lead_capture_agent",
      name: "AI lead-capture & booking agent",
      fit_reason: "Captures the lead into your CRM.",
      whats_included: ["Tool-calling webhooks"],
      price_band: { label: "Fixed scope", low_usd: 400, high_usd: 1000 },
      confidence: 0.7,
    },
  ],
  solution: {
    summary: "A grounded agent over your data with eval and observability.",
    architecture_steps: ["Ingest", "Answer with citations", "Capture lead"],
    stack_notes: ["RAG", "Tool-calling"],
  },
  timeline: [
    { name: "Discovery", duration: "1-2 days", deliverable: "Scope" },
    { name: "Build", duration: "2-4 days", deliverable: "Agent + actions" },
  ],
  grounded: true,
  citations: [
    { n: 1, doc_id: "service-rag", title: "Support agent", source: "x.md", score: 0.8 },
  ],
  cost_usd: 0,
  latency_ms: 12,
  provider: "fake",
  model: "fake-1",
};
