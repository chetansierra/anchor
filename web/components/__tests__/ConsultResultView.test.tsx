import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { ConsultResultView } from "@/components/ConsultResultView";
import { sampleResult } from "./fixtures";

describe("ConsultResultView", () => {
  it("renders all four artifact types from a ConsultResult", () => {
    render(<ConsultResultView result={sampleResult} problem="docs chatbot" />);

    // 1. matched service cards (no price shown)
    expect(screen.getByText("Website AI support agent")).toBeInTheDocument();
    expect(screen.getByText("AI lead-capture & booking agent")).toBeInTheDocument();

    // 2. solution as outcome bullets ("What you'll get")
    expect(screen.getByText("What you'll get")).toBeInTheDocument();
    expect(screen.getByText("Instant answers from your docs")).toBeInTheDocument();

    // 3. timeline
    expect(screen.getByText("Rough timeline")).toBeInTheDocument();
    expect(screen.getByText("Discovery")).toBeInTheDocument();

    // 4. lead capture CTA (no eval/proof numbers on the page)
    expect(screen.getByText("Book a call")).toBeInTheDocument();
  });

  it("does not show eval numbers or prices on the page", () => {
    render(<ConsultResultView result={sampleResult} problem="docs chatbot" />);
    expect(screen.queryByText(/92\.7%|accuracy|labeled cases/i)).toBeNull();
    expect(screen.queryByText(/\$\d/)).toBeNull(); // price hidden for now
  });
});
