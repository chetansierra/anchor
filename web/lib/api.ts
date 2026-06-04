// Typed client for the FastAPI consult backend (browser -> FastAPI, direct CORS).

import { streamSSE } from "./sse";
import type { CatalogService, ConsultResult, StageFrame } from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE?.replace(/\/$/, "") || "http://127.0.0.1:8000";

export interface ConsultHandlers {
  onStage: (frame: StageFrame) => void;
  onResult: (result: ConsultResult) => void;
  onError: (message: string) => void;
  onDone: () => void;
}

/** Stream a consultation: named reasoning stages, then the structured result. */
export async function streamConsult(
  problem: string,
  handlers: ConsultHandlers,
  signal?: AbortSignal,
): Promise<void> {
  try {
    await streamSSE(
      `${API_BASE}/consult/stream`,
      { problem },
      {
        signal,
        onFrame: ({ event, data }) => {
          if (event === "stage") handlers.onStage(data as StageFrame);
          else if (event === "result") handlers.onResult(data as ConsultResult);
          else if (event === "error") {
            const d = data as { detail?: string };
            handlers.onError(d?.detail || "Something went wrong.");
          } else if (event === "done") handlers.onDone();
        },
      },
    );
  } catch (err) {
    if ((err as Error)?.name === "AbortError") return;
    handlers.onError((err as Error)?.message || "Could not reach the consultant.");
  }
}

export interface LeadPayload {
  email: string;
  name?: string;
  problem?: string;
  services?: string[];
}

export async function submitLead(payload: LeadPayload): Promise<{ id: string }> {
  const res = await fetch(`${API_BASE}/consult/lead`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    let detail = "Could not capture your details — please try again.";
    try {
      const j = await res.json();
      if (j?.detail) detail = j.detail;
    } catch {
      /* keep default */
    }
    throw new Error(detail);
  }
  return res.json();
}

export async function getCatalog(): Promise<CatalogService[]> {
  const res = await fetch(`${API_BASE}/consult/catalog`, { cache: "no-store" });
  if (!res.ok) return [];
  const data = await res.json();
  return data.services ?? [];
}
