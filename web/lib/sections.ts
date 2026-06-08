// Main result sections — shared by ConsultResultView (anchors) and the
// right-rail table of contents. Top-level categories only, no sub-items.
export const RESULT_SECTIONS = [
  { id: "sec-services", label: "Services" },
  { id: "sec-solution", label: "What you'll get" },
  { id: "sec-timeline", label: "Timeline" },
  { id: "sec-contact", label: "Book a call" },
  { id: "sec-example", label: "Deployed example" },
] as const;
