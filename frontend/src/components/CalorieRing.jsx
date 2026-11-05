import { MACRO_COLORS } from "../utils/constants";

/** "Today's plate": the outer arc is calories against target; the three inner arcs are
 *  protein, carbs and fat against their targets. Colours match every other chart. */
export function CalorieRing({ consumed = 0, target, protein, carbs, fat, size = 248 }) {
  const c = size / 2;
  const rings = [
    { r: c - 14, stroke: 16, value: consumed, max: target, color: MACRO_COLORS.calories, track: "#E7F3E9" },
    { r: c - 38, stroke: 7, value: protein?.value, max: protein?.target, color: MACRO_COLORS.protein, track: "#DCEBF2" },
    { r: c - 50, stroke: 7, value: carbs?.value, max: carbs?.target, color: MACRO_COLORS.carbs, track: "#F7ECD3" },
    { r: c - 62, stroke: 7, value: fat?.value, max: fat?.target, color: MACRO_COLORS.fat, track: "#F1E3EE" },
  ];
  const remaining = target ? Math.round(target - consumed) : null;
  const over = remaining != null && remaining < 0;

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90" aria-hidden>
        {rings.map((ring, i) => {
          const full = 2 * Math.PI * ring.r;
          const pct = ring.max ? Math.min((ring.value || 0) / ring.max, 1) : 0;
          const offset = full * (1 - pct);
          return (
            <g key={i}>
              <circle cx={c} cy={c} r={ring.r} fill="none" stroke={ring.track} strokeWidth={ring.stroke} />
              <circle cx={c} cy={c} r={ring.r} fill="none" stroke={i === 0 && over ? "#B4412F" : ring.color}
                strokeWidth={ring.stroke} strokeLinecap="round" strokeDasharray={full}
                className="animate-ring-in" style={{ "--ring-full": full, "--ring-offset": offset, strokeDashoffset: offset, animationDelay: `${i * 90}ms` }} />
            </g>
          );
        })}
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
        {remaining == null ? (
          <>
            <span className="num font-display text-4xl font-semibold">{Math.round(consumed)}</span>
            <span className="text-sm text-slate">kcal eaten</span>
          </>
        ) : (
          <>
            <span className={`num font-display text-[44px] font-semibold leading-none ${over ? "text-alert" : "text-ink"}`}>
              {Math.abs(remaining).toLocaleString()}
            </span>
            <span className="mt-1 text-sm text-slate">{over ? "kcal over target" : "kcal left today"}</span>
          </>
        )}
      </div>
      <p className="sr-only">
        {Math.round(consumed)} of {target ?? "unknown"} kilocalories eaten today.
      </p>
    </div>
  );
}
