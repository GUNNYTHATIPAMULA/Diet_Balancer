import { MACRO_COLORS } from "../utils/constants";

export function TargetsBreakdown({ targets }) {
  const rows = [
    { label: "BMR (at rest)", value: targets.bmr },
    { label: "Maintenance (TDEE)", value: targets.tdee, note: `×${targets.activity_factor}` },
    { label: "Goal adjustment", value: targets.goal_adjustment, signed: true },
  ];
  return (
    <div className="space-y-5">
      <div className="flex items-end justify-between rounded-2xl bg-canopy px-5 py-4 text-white">
        <div>
          <p className="text-sm text-sprout">Daily calorie target</p>
          <p className="num font-display text-4xl font-semibold">{targets.calorie_target.toLocaleString()} <span className="text-lg font-medium text-sprout">kcal</span></p>
        </div>
        <p className="text-right text-xs text-sprout">{targets.formula}</p>
      </div>
      <dl className="divide-y divide-line rounded-2xl border border-line">
        {rows.map((r) => (
          <div key={r.label} className="flex items-center justify-between px-4 py-3 text-[15px]">
            <dt className="text-slate">{r.label} {r.note && <span className="text-slate-light">{r.note}</span>}</dt>
            <dd className="num font-semibold">{r.signed && r.value > 0 ? "+" : ""}{r.value.toLocaleString()} kcal</dd>
          </div>
        ))}
      </dl>
      <div className="grid grid-cols-3 gap-2">
        {[["Protein", targets.protein_g, MACRO_COLORS.protein], ["Carbs", targets.carbs_g, MACRO_COLORS.carbs], ["Fat", targets.fat_g, MACRO_COLORS.fat]].map(([label, v, color]) => (
          <div key={label} className="rounded-2xl border border-line px-3 py-3">
            <span className="mb-2 block h-1.5 w-8 rounded-full" style={{ background: color }} aria-hidden />
            <p className="num font-display text-2xl font-semibold">{v} g</p>
            <p className="text-sm text-slate">{label}</p>
          </div>
        ))}
      </div>
      <details className="rounded-2xl bg-mist px-4 py-3 text-sm">
        <summary className="cursor-pointer font-semibold text-ink">How this was calculated</summary>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-slate">
          {targets.explanation.map((line) => <li key={line}>{line}</li>)}
        </ul>
      </details>
    </div>
  );
}
