import { useState } from "react";
import { ChevronLeft, ChevronRight, BarChart3 } from "lucide-react";
import { reportsApi } from "../api/nutrition";
import { errorMessage } from "../api/client";
import { useAsync } from "../hooks/useAsync";
import { formatDay, shiftDate, todayISO } from "../utils/format";
import { PageHeader } from "../components/PageHeader";
import { MacroTrendChart, TargetVsActualChart } from "../components/charts";
import { Button } from "../components/ui/Button";
import { Segmented } from "../components/ui/Segmented";
import { EmptyState, ErrorState, PageSkeleton } from "../components/ui/Feedback";

export default function ReportsPage() {
  const [period, setPeriod] = useState("weekly");
  const [weekEnd, setWeekEnd] = useState(todayISO());
  const now = new Date();
  const [ym, setYm] = useState({ year: now.getFullYear(), month: now.getMonth() + 1 });
  const { data, error, loading, reload } = useAsync(
    () => (period === "weekly" ? reportsApi.weekly(weekEnd) : reportsApi.monthly(ym.year, ym.month)),
    [period, weekEnd, ym.year, ym.month],
  );

  const shift = (dir) => {
    if (period === "weekly") return setWeekEnd(shiftDate(weekEnd, 7 * dir));
    const d = new Date(ym.year, ym.month - 1 + dir, 1);
    setYm({ year: d.getFullYear(), month: d.getMonth() + 1 });
  };
  const atLatest = period === "weekly" ? weekEnd >= todayISO() : ym.year === now.getFullYear() && ym.month === now.getMonth() + 1;
  const label = data
    ? period === "weekly"
      ? `${formatDay(data.start_date, { day: "numeric", month: "short" })} – ${formatDay(data.end_date, { day: "numeric", month: "short", year: "numeric" })}`
      : new Date(ym.year, ym.month - 1, 1).toLocaleDateString(undefined, { month: "long", year: "numeric" })
    : "";

  return (
    <div>
      <PageHeader title="Reports" subtitle="How your intake compares with your current target over time."
        actions={<Segmented label="Period" value={period} onChange={setPeriod} options={[{ value: "weekly", label: "Week" }, { value: "monthly", label: "Month" }]} />} />
      <div className="mb-5 flex items-center gap-2">
        <Button variant="secondary" size="icon" onClick={() => shift(-1)} aria-label="Previous period"><ChevronLeft className="h-4 w-4" /></Button>
        <Button variant="secondary" size="icon" onClick={() => shift(1)} disabled={atLatest} aria-label="Next period"><ChevronRight className="h-4 w-4" /></Button>
        <p className="ml-2 font-display text-lg font-semibold">{label}</p>
      </div>

      {loading && !data ? <PageSkeleton /> : error ? <ErrorState message={errorMessage(error)} onRetry={reload} /> : (
        <div className="space-y-6">
          <dl className="grid grid-cols-2 gap-3 md:grid-cols-4">
            {[
              ["Average intake", data.days_logged ? `${Math.round(data.average_calories).toLocaleString()} kcal` : "—", data.calorie_target ? `Target ${data.calorie_target.toLocaleString()} kcal` : "No target set"],
              ["Days logged", `${data.days_logged} of ${data.days.length}`, "Days with at least one entry"],
              ["Days on target", data.calorie_target ? `${data.days_on_target}` : "—", data.on_target_rule],
              ["Dispensed", `${data.dispensed_count} times`, `${Math.round(data.dispensed_total_g).toLocaleString()} g measured by the scale`],
            ].map(([k, v, hint]) => (
              <div key={k} className="panel p-4">
                <dt className="text-sm text-slate">{k}</dt>
                <dd className="num mt-1 font-display text-2xl font-semibold">{v}</dd>
                <dd className="mt-1 text-xs text-slate">{hint}</dd>
              </div>
            ))}
          </dl>

          {data.days_logged === 0 ? (
            <div className="panel"><EmptyState icon={BarChart3} title="Nothing logged in this period">Log meals in the Food Tracker and they’ll appear here.</EmptyState></div>
          ) : (
            <>
              <section className="panel p-6">
                <h2 className="mb-4 text-lg font-semibold">Calories vs target</h2>
                <TargetVsActualChart days={data.days} target={data.calorie_target} height={280} />
                <p className="mt-2 text-xs text-slate">Bars turn rose when a day is more than 10% over target.</p>
              </section>
              <div className="grid gap-6 lg:grid-cols-[1.5fr_1fr]">
                <section className="panel p-6">
                  <h2 className="mb-4 text-lg font-semibold">Macros per day</h2>
                  <MacroTrendChart days={data.days} height={260} />
                  <p className="num mt-3 text-sm text-slate">Averages on logged days: protein {data.average_protein_g} g · carbs {data.average_carbs_g} g · fat {data.average_fat_g} g</p>
                </section>
                <section className="panel p-6">
                  <h2 className="mb-4 text-lg font-semibold">Most logged foods</h2>
                  <ol className="space-y-3">
                    {data.top_foods.map((f, i) => (
                      <li key={f.food_name} className="flex items-center gap-3">
                        <span className="num grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-sprout-light text-sm font-semibold text-canopy">{i + 1}</span>
                        <div className="min-w-0 flex-1">
                          <p className="truncate font-semibold">{f.food_name}</p>
                          <p className="num text-xs text-slate">{f.times_logged}× · {Math.round(f.total_quantity_g)} g · {Math.round(f.total_calories)} kcal</p>
                        </div>
                      </li>
                    ))}
                  </ol>
                </section>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
