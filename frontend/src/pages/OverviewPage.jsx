import { useState } from "react";
import { Link } from "react-router-dom";
import { CheckCircle2, Cpu, Lightbulb, Plus, Scale } from "lucide-react";
import { nutritionApi } from "../api/nutrition";
import { mealsApi } from "../api/meals";
import { devicesApi } from "../api/devices";
import { errorMessage } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { useAsync } from "../hooks/useAsync";
import { firstName, formatDay, greeting, relativeTime, todayISO } from "../utils/format";
import { MACRO_COLORS } from "../utils/constants";
import { CalorieRing } from "../components/CalorieRing";
import { MacroBar } from "../components/MacroBar";
import { MealSection } from "../components/MealSection";
import { AddMealModal } from "../components/AddMealModal";
import { ConfirmDialog } from "../components/ui/Modal";
import { Button } from "../components/ui/Button";
import { Badge, ErrorState, PageSkeleton } from "../components/ui/Feedback";
import { MacroDonut, MacroTrendChart, MealCaloriesChart, TargetVsActualChart } from "../components/charts";
import { Disclaimer } from "../components/Disclaimer";

function Panel({ title, action, children, className = "" }) {
  return (
    <section className={`panel p-5 sm:p-6 ${className}`}>
      {(title || action) && (
        <div className="mb-4 flex items-center justify-between gap-3">
          <h2 className="text-lg font-semibold">{title}</h2>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

export default function OverviewPage() {
  const { user } = useAuth();
  const toast = useToast();
  const today = todayISO();
  const { data, error, loading, reload } = useAsync(async () => {
    const [summary, weekly, recs, devices] = await Promise.all([
      nutritionApi.summary(today), mealsApi.weekly(today), nutritionApi.recommendations(today, 3), devicesApi.list(),
    ]);
    return { summary, weekly, recs, devices };
  }, [today]);
  const [modal, setModal] = useState({ open: false, meal: "breakfast", entry: null });
  const [deleting, setDeleting] = useState(null);

  if (loading && !data) return <PageSkeleton />;
  if (error && !data) return <ErrorState message={errorMessage(error)} onRetry={reload} />;

  const { summary, weekly, recs, devices } = data;
  const t = summary.targets;
  const c = summary.consumed;
  const device = devices[0];
  const refresh = () => reload({ silent: true });

  const confirmDelete = async () => {
    try {
      await mealsApi.remove(deleting.id);
      toast.success(`${deleting.food_name} removed.`);
      setDeleting(null);
      refresh();
    } catch (e) {
      toast.error(errorMessage(e));
    }
  };

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-[15px] text-slate">{formatDay(today)}</p>
          <h1 className="text-[30px] font-semibold leading-tight sm:text-[34px]">{greeting()}, {firstName(user?.full_name)}</h1>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="green"><CheckCircle2 className="h-3.5 w-3.5" aria-hidden />Profile complete</Badge>
          {t && <Badge tone="neutral">Daily target {t.calorie_target.toLocaleString()} kcal</Badge>}
          <Button size="sm" icon={Plus} onClick={() => setModal({ open: true, meal: "snacks", entry: null })}>Log food</Button>
        </div>
      </header>

      {/* Today's plate */}
      <section className="panel grid gap-8 p-6 sm:p-8 lg:grid-cols-[auto_1fr] lg:items-center">
        <div className="mx-auto">
          <CalorieRing consumed={c.calories} target={t?.calorie_target}
            protein={{ value: c.protein_g, target: t?.protein_g }} carbs={{ value: c.carbs_g, target: t?.carbs_g }} fat={{ value: c.fat_g, target: t?.fat_g }} />
        </div>
        <div className="space-y-6">
          <dl className="grid grid-cols-3 divide-x divide-line rounded-2xl bg-mist py-4">
            {[["Target", t?.calorie_target], ["Eaten", Math.round(c.calories)], ["Remaining", t ? Math.round(t.calorie_target - c.calories) : null]].map(([label, v]) => (
              <div key={label} className="px-4 text-center">
                <dt className="text-sm text-slate">{label}</dt>
                <dd className={`num font-display text-2xl font-semibold sm:text-3xl ${label === "Remaining" && v < 0 ? "text-alert" : ""}`}>{v == null ? "—" : v.toLocaleString()}</dd>
                <dd className="text-xs text-slate-light">kcal</dd>
              </div>
            ))}
          </dl>
          <div className="grid gap-4 sm:grid-cols-3">
            <MacroBar label="Protein" value={c.protein_g} target={t?.protein_g} color={MACRO_COLORS.protein} />
            <MacroBar label="Carbs" value={c.carbs_g} target={t?.carbs_g} color={MACRO_COLORS.carbs} />
            <MacroBar label="Fat" value={c.fat_g} target={t?.fat_g} color={MACRO_COLORS.fat} />
          </div>
        </div>
      </section>

      <div className="grid gap-6 lg:grid-cols-5">
        <Panel title="Today’s meals" className="lg:col-span-3" action={<Link to="/food" className="text-sm font-semibold text-canopy hover:underline">Open food tracker</Link>}>
          <div className="space-y-3">
            {summary.meals.map((g) => (
              <MealSection key={g.meal_type} group={g} compact onAdd={(meal) => setModal({ open: true, meal, entry: null })}
                onEdit={(entry) => setModal({ open: true, meal: entry.meal_type, entry })} onDelete={setDeleting} />
            ))}
          </div>
        </Panel>

        <div className="space-y-6 lg:col-span-2">
          <Panel title="Suggested next" action={<Link to="/recommendations" className="text-sm font-semibold text-canopy hover:underline">See all</Link>}>
            <p className="mb-3 text-sm text-slate">{recs.message}</p>
            <ul className="space-y-2">
              {recs.items.map((r) => (
                <li key={r.food_id} className="flex items-center justify-between gap-3 rounded-2xl border border-line px-3.5 py-3">
                  <div className="min-w-0">
                    <p className="truncate font-semibold">{r.food_name}</p>
                    <p className="num text-xs text-slate">{r.suggested_quantity_g} g · {Math.round(r.calories)} kcal · P {r.protein_g} g</p>
                  </div>
                  <Lightbulb className="h-4 w-4 shrink-0 text-wheat" aria-hidden />
                </li>
              ))}
              {recs.items.length === 0 && <p className="text-sm text-slate">No suggestions match your preferences right now.</p>}
            </ul>
          </Panel>

          <Panel title="Smart dispenser" action={<Link to="/dispenser" className="text-sm font-semibold text-canopy hover:underline">Open</Link>}>
            {device ? (
              <div className="flex items-center gap-3">
                <span className={`grid h-11 w-11 place-items-center rounded-2xl ${device.is_online ? "bg-sprout-light text-canopy" : "bg-mist text-slate"}`}><Cpu className="h-5 w-5" aria-hidden /></span>
                <div className="min-w-0 flex-1">
                  <p className="truncate font-semibold">{device.name}</p>
                  <p className="text-sm text-slate">{device.is_online ? "Online" : "Offline"} · last seen {relativeTime(device.last_heartbeat_at)}</p>
                </div>
                {device.last_weight_g != null && device.is_online && (
                  <span className="num flex items-center gap-1 text-sm font-semibold"><Scale className="h-4 w-4 text-slate" aria-hidden />{device.last_weight_g} g</span>
                )}
              </div>
            ) : (
              <p className="text-sm text-slate">No dispenser connected yet. <Link to="/dispenser" className="font-semibold text-canopy hover:underline">Add your ESP32 dispenser</Link>.</p>
            )}
          </Panel>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel title="Calories by meal today"><MealCaloriesChart meals={summary.meals} /></Panel>
        <Panel title="Macro split today"><MacroDonut split={summary.macro_split_percent} totals={c} /></Panel>
        <Panel title="Target vs actual, last 7 days"><TargetVsActualChart days={weekly.days} target={t?.calorie_target} /></Panel>
        <Panel title="Weekly macro trend"><MacroTrendChart days={weekly.days} /></Panel>
      </div>

      <Disclaimer />

      <AddMealModal open={modal.open} day={today} defaultMeal={modal.meal} entry={modal.entry}
        onClose={() => setModal((m) => ({ ...m, open: false }))} onSaved={refresh} />
      <ConfirmDialog open={!!deleting} title="Remove this entry?" confirmLabel="Remove"
        message={deleting ? `${deleting.food_name} (${deleting.quantity_g} g) will be removed from today’s log.` : ""}
        onConfirm={confirmDelete} onCancel={() => setDeleting(null)} />
    </div>
  );
}
