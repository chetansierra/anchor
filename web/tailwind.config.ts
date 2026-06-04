import type { Config } from "tailwindcss";

// Brand tokens mirrored from the existing FastAPI portfolio (app/static/portfolio.html)
// so the new hero feels continuous with the retained Nimbus demo + case study.
const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: { DEFAULT: "#0f5f36", ink: "#0c4f2d", soft: "#22c55e" },
        bg: "#f6fbf7",
        surface: "#ffffff",
        soft: "#eaf6ec",
        ink: "#123224",
        muted: "#3d5f4e",
        line: { DEFAULT: "#d6e7db", strong: "#aecdb9" },
      },
      borderRadius: {
        card: "16px",
      },
      boxShadow: {
        card: "0 1px 2px rgba(15,95,54,.04), 0 8px 24px rgba(15,95,54,.06)",
        lift: "0 6px 18px rgba(15,95,54,.10)",
      },
      keyframes: {
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        pulse_dot: {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.3" },
        },
      },
      animation: {
        "fade-up": "fade-up .35s ease both",
        "pulse-dot": "pulse_dot 1.2s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};

export default config;
