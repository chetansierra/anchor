"use client";

import { useEffect, useState } from "react";
import { RESULT_SECTIONS } from "@/lib/sections";

// A reader-style "on this page" index. Appears alongside the rendered result,
// highlights the section currently in view (scrollspy), and jumps on click.
// Main sections only — never sub-items.
export function ResultToc() {
  const [active, setActive] = useState<string>(RESULT_SECTIONS[0].id);

  useEffect(() => {
    const els = RESULT_SECTIONS.map((s) => document.getElementById(s.id)).filter(
      (el): el is HTMLElement => el !== null,
    );
    if (els.length === 0) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible[0]) setActive(visible[0].target.id);
      },
      { rootMargin: "-15% 0px -70% 0px", threshold: 0 },
    );
    els.forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, []);

  return (
    <nav className="sticky top-24 animate-fade-up">
      <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-muted/70">
        On this page
      </p>
      <ul className="border-l border-line">
        {RESULT_SECTIONS.map((s) => {
          const isActive = active === s.id;
          return (
            <li key={s.id}>
              <a
                href={`#${s.id}`}
                onClick={(e) => {
                  e.preventDefault();
                  document.getElementById(s.id)?.scrollIntoView({ behavior: "smooth", block: "start" });
                }}
                className={
                  "-ml-px block border-l-2 py-1.5 pl-3 text-[13px] transition-colors " +
                  (isActive
                    ? "border-brand font-medium text-brand"
                    : "border-transparent text-muted hover:text-ink")
                }
              >
                {s.label}
              </a>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
