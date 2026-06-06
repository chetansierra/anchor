"use client";

import { useEffect } from "react";
import { API_BASE } from "@/lib/api";

// Mounts the existing FastAPI RAG support widget (Nimbus) as a floating launcher
// at the bottom-right of the page, with a one-time attention pulse to draw the
// eye. The widget is shadow-DOM isolated; we configure it via
// window.AnchorWidgetConfig because a dynamically injected <script> has no
// document.currentScript to read data-* attributes from.
export function RagWidget() {
  useEffect(() => {
    if (document.querySelector("script[data-anchor-loader]")) return;

    (window as unknown as { AnchorWidgetConfig?: Record<string, string> }).AnchorWidgetConfig = {
      api: API_BASE,
      business: "Nimbus",
      color: "#0f5f36",
      position: "bottom-right",
      machinery: "off",
      attention: "on",
    };

    const s = document.createElement("script");
    s.src = `${API_BASE}/widget.js`;
    s.async = true;
    s.dataset.anchorLoader = "1";
    document.body.appendChild(s);
    // Intentionally no cleanup: the widget mounts a persistent shadow host and
    // sets its own double-mount guard, so it lives for the page session.
  }, []);

  return null;
}
