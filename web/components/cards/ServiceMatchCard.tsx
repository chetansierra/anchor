import type { ServiceMatch } from "@/lib/types";

export function ServiceMatchCard({
  service,
  index,
}: {
  service: ServiceMatch;
  index: number;
}) {
  return (
    <div className="rounded-card border border-line bg-surface shadow-card p-5 transition-shadow hover:shadow-lift">
      <div className="flex items-start gap-3">
        <span className="flex h-7 w-7 flex-none items-center justify-center rounded-full bg-brand text-sm font-semibold text-white">
          {index}
        </span>
        <div className="min-w-0">
          <h4 className="text-base font-semibold text-ink">{service.name}</h4>
          <p className="mt-1 text-[14px] leading-relaxed text-muted">{service.fit_reason}</p>
          {service.whats_included.length > 0 && (
            <ul className="mt-3 space-y-1.5">
              {/* crisp, end-product outcomes — top few only */}
              {service.whats_included.slice(0, 3).map((item, i) => (
                <li key={i} className="flex gap-2 text-[13.5px] text-ink/90">
                  <span className="mt-[7px] h-1.5 w-1.5 flex-none rounded-full bg-brand-soft" />
                  {item}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
