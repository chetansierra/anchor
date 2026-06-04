import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { ConsultResultView } from "@/components/ConsultResultView";
import { sampleResult } from "./fixtures";

describe("ConsultResultView", () => {
  it("renders all four artifact types from a ConsultResult", () => {
    render(<ConsultResultView result={sampleResult} problem="docs chatbot" />);

    // 1. matched service cards
    expect(screen.getByText("Website AI support agent")).toBeInTheDocument();
    expect(screen.getByText("AI lead-capture & booking agent")).toBeInTheDocument();
    expect(screen.getByText("$300–$800")).toBeInTheDocument();

    // 2. solution sketch
    expect(screen.getByText("How I'd build it")).toBeInTheDocument();
    expect(screen.getByText("Capture lead")).toBeInTheDocument();

    // 3. timeline
    expect(screen.getByText("Rough timeline")).toBeInTheDocument();
    expect(screen.getByText("Discovery")).toBeInTheDocument();

    // 4. proof + lead capture CTA
    expect(
      screen.getByText("92.7% answer accuracy on 41 labeled cases"),
    ).toBeInTheDocument();
    expect(screen.getByText("Book a call")).toBeInTheDocument();
  });
});
