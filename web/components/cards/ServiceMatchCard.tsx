import type { ServiceMatch } from "@/lib/types";

function priceLabel(low: number, high: number): string {
  const fmt = (n: number) => `$${n.toLocaleString()}`;
  return high > low ? `${fmt(low)}–${fmt(high)}` : `${fmt(low)}+`;
}

export function ServiceMatchCard({ service }: { service: ServiceMatch }) {
  return (
    <div className="rounded-card border border-line bg-surface shadow-card p-5 transition-shadow hover:shadow-lift">
      <div className="flex items-start justify-between gap-4">
        <h4 className="text-base font-semibold text-ink">{service.name}</h4>
        <span className="whitespace-nowrap rounded-lg bg-soft px-2.5 py-1 text-sm font-semibold text-brand-ink">
          {priceLabel(service.price_band.low_usd, service.price_band.high_usd)}
        </span>
      </div>
      <p className="mt-2 text-[14px] leading-relaxed text-muted">{service.fit_reason}</p>
      {service.whats_included.length > 0 && (
        <ul className="mt-3 space-y-1.5">
          {/* keep it scannable — top few inclusions only */}
          {service.whats_included.slice(0, 3).map((item, i) => (
            <li key={i} className="flex gap-2 text-[13.5px] text-ink/90">
              <span className="mt-[7px] h-1.5 w-1.5 flex-none rounded-full bg-brand-soft" />
              {item}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
