import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { ThinkingStepper } from "@/components/ThinkingStepper";
import type { Stage } from "@/lib/types";

describe("ThinkingStepper", () => {
  it("renders nothing when there are no stages", () => {
    const { container } = render(<ThinkingStepper stages={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders a row per stage with its label and a retrieval count", () => {
    const stages: Stage[] = [
      { step: "understanding", label: "Understanding your problem", status: "done" },
      { step: "matching", label: "Matching services", status: "done", docs: 5 },
      { step: "drafting", label: "Drafting an approach", status: "active" },
    ];
    render(<ThinkingStepper stages={stages} />);

    expect(screen.getByText("Understanding your problem")).toBeInTheDocument();
    expect(screen.getByText("Matching services")).toBeInTheDocument();
    expect(screen.getByText("Drafting an approach")).toBeInTheDocument();
    expect(screen.getByText("5 sources")).toBeInTheDocument();
  });
});
