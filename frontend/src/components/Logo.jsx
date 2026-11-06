export function Logo({ className = "", light = false }) {
  return (
    <span className={`inline-flex items-center gap-2.5 ${className}`}>
      <svg viewBox="0 0 32 32" className="h-8 w-8" aria-hidden>
        <circle cx="16" cy="16" r="15" fill={light ? "#CFE8D3" : "#1F5F3F"} />
        <path d="M16 7c-5 3-7 7-6 12 4 0 8-2 10-6-2 4-5 7-8 9 6 1 10-4 10-9 0-3-2-5-6-6z" fill={light ? "#1F5F3F" : "#CFE8D3"} />
      </svg>
      <span className={`font-display text-xl font-semibold tracking-tight ${light ? "text-white" : "text-ink"}`}>Diet Balancer</span>
    </span>
  );
}
