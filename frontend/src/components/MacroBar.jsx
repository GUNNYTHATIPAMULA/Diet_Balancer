export function MacroBar({ label, value = 0, target, color, unit = "g" }) {
  const pct = target ? Math.min((value / target) * 100, 100) : 0;
  return (
    <div>
      <div className="mb-1.5 flex items-baseline justify-between text-sm">
        <span className="flex items-center gap-2 font-semibold text-ink">
          <span className="h-2.5 w-2.5 rounded-full" style={{ background: color }} aria-hidden />
          {label}
        </span>
        <span className="num text-slate">
          <span className="font-semibold text-ink">{Math.round(value)}</span>
          {target ? ` / ${target} ${unit}` : ` ${unit}`}
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-mist" role="progressbar" aria-label={label} aria-valuenow={Math.round(value)} aria-valuemax={target || undefined}>
        <div className="h-full rounded-full transition-[width] duration-700" style={{ width: `${pct}%`, background: color }} />
      </div>
    </div>
  );
}
