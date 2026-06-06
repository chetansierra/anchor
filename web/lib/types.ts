// TypeScript mirror of the backend ConsultResult schema (app/models.py).
// Hand-kept in sync; if the Python schema changes, update here too.

export interface PriceBand {
  label: string;
  low_usd: number;
  high_usd: number;
}

export interface ServiceMatch {
  service_id: string;
  name: string;
  fit_reason: string;
  whats_included: string[];
  price_band: PriceBand;
  confidence: number;
}

export interface TimelinePhase {
  name: string;
  duration: string;
  deliverable: string;
}

export interface SolutionSketch {
  summary: string;
  architecture_steps: string[];
  stack_notes: string[];
}

export interface Citation {
  n: number;
  doc_id: string;
  title: string;
  source: string;
  score: number;
}

export interface ConsultResult {
  problem_restatement: string;
  services: ServiceMatch[];
  solution: SolutionSketch;
  timeline: TimelinePhase[];
  grounded: boolean;
  citations: Citation[];
  cost_usd: number;
  latency_ms: number;
  provider: string;
  model: string;
}

// One staged-reasoning step surfaced over SSE.
export type StageStatus = "active" | "done";

export interface Stage {
  step: string;
  label: string;
  status: StageStatus;
  docs?: number;
}

// Raw SSE `stage` frame payload from the backend.
export interface StageFrame {
  step: string;
  label?: string;
  status: "start" | "done";
  meta?: { docs?: number };
}

export interface CatalogService {
  id: string;
  name: string;
  price_band: PriceBand;
  whats_included: string[];
}
