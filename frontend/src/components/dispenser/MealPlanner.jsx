import { useEffect, useMemo, useState } from "react";
import { ChefHat, Info, Minus, Plus, RefreshCw, Sparkles } from "lucide-react";
import { mealPlansApi } from "../../api/devices";
import { nutritionApi } from "../../api/nutrition";
import { errorMessage } from "../../api/client";
import { useToast } from "../../context/ToastContext";
import { MEAL_TYPES, MACRO_COLORS } from "../../utils/constants";
import { todayISO } from "../../utils/format";
import { CategoryTags } from "../../utils/nutrition";
import { Button } from "../ui/Button";
import { Skeleton } from "../ui/Feedback";

const MACROS = [
  ["kcal", "Calories", "kcal", MACRO_COLORS.calories],
  ["protein", "Protein", "g", MACRO_COLORS.protein],
  ["carbs", "Carbs", "g", MACRO_COLORS.carbs],
  ["fat", "Fat", "g", MACRO_COLORS.fat],
];

function scaled(item, grams) {
  const f = item.grams ? grams / item.grams : 0;
  return Object.fromEntries(Object.entries(item.nutrition).map(([k, v]) => [k, v * f]));
}

/** Remaining today → Generate My Meal → review/adjust portions → Serve Meal. */
export function MealPlanner({ device, defaultMeal, disabledReason, onServed, refreshKey }) {
  const toast = useToast();
  const [mealType, setMealType] = useState(defaultMeal);
  const [remaining, setRemaining] = useState(null);
  const [plan, setPlan] = useState(null);
  const [grams, setGrams] = useState({});
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  useEffect(() => setMealType(defaultMeal), [defaultMeal]);
  useEffect(() => {
    nutritionApi.summary(todayISO())
      .then((s) => setRemaining(s.remaining ? { kcal: s.remaining.calories, protein: s.remaining.protein_g, carbs: s.remaining.carbs_g, fat: s.remaining.fat_g } : null))
      .catch(() => setRemaining(null));
  }, [refreshKey]);

  const generate = async () => {
    setBusy("generate");
    setError("");
    try {
      const p = await mealPlansApi.generate({ device_id: device.id, meal_type: mealType, consumed_on: todayISO() });
      setPlan(p);
      setGrams(Object.fromEntries(p.items.map((i) => [i.container_id, i.grams])));
      setRemaining(p.remaining_today);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy("");
    }
  };

  const items = plan?.items || [];
  const totals = useMemo(() => {
    const t = { kcal: 0, protein: 0, carbs: 0, fat: 0 };
    items.forEach((i) => {
      const n = scaled(i, Number(grams[i.container_id] || 0));
      Object.keys(t).forEach((k) => (t[k] += n[k] || 0));
    });
    return t;
  }, [items, grams]);

  const adjust = (id, delta) => setGrams((g) => ({ ...g, [id]: Math.max(0, Math.min(500, Math.round((Number(g[id]) || 0) + delta))) }));

  const serve = async () => {
    const chosen = items.map((i) => ({ container_id: i.container_id, grams: Number(grams[i.container_id] || 0) }));
    if (!chosen.some((i) => i.grams > 0)) return setError("Choose at least one food to serve.");
    const bad = chosen.find((i) => i.grams > 0 && (i.grams < 5 || i.grams > 500));
    if (bad) return setError("Each portion must be between 5 and 500 g (or 0 to skip it).");
    setBusy("serve");
    setError("");
    try {
      const served = await mealPlansApi.serve(plan.id, chosen);
      toast.success("Serving your meal. The dispenser measures each food as it goes.");
      setPlan(null);
      onServed(served);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy("");
    }
  };

  const target = plan?.meal_target;
  return (
    <section className="panel overflow-hidden" aria-labelledby="meal-planner">
      <div className="flex flex-col gap-4 border-b border-line bg-gradient-to-br from-sprout-light/70 to-white p-6 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 id="meal-planner" className="flex items-center gap-2 text-xl font-semibold"><ChefHat className="h-5 w-5 text-canopy" aria-hidden />Your meal</h2>
          <p className="mt-1 text-sm text-slate">Portions from your containers, balanced against what’s left of today’s targets.</p>
        </div>
        <div className="flex items-center gap-2">
          <select value={mealType} onChange={(e) => setMealType(e.target.value)} className="field-input w-auto py-2" aria-label="Meal">
            {MEAL_TYPES.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
          </select>
          <Button icon={plan ? RefreshCw : Sparkles} loading={busy === "generate"} onClick={generate}>
            {plan ? "Regenerate" : "Generate My Meal"}
          </Button>
        </div>
      </div>

      <div className="p-6">
        <p className="mb-2 text-sm font-semibold text-slate">Left today</p>
        {remaining ? (
          <dl className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {MACROS.map(([k, label, unit, color]) => (
              <div key={k} className="rounded-2xl bg-mist px-4 py-3">
                <dt className="flex items-center gap-1.5 text-xs text-slate"><span className="h-2 w-2 rounded-full" style={{ background: color }} aria-hidden />{label}</dt>
                <dd className={`num font-display text-xl font-semibold ${remaining[k] < 0 ? "text-alert" : ""}`}>
                  {Math.round(remaining[k])} <span className="text-sm font-medium text-slate">{unit}</span>
                </dd>
              </div>
            ))}
          </dl>
        ) : <Skeleton className="h-16" />}

        {error && <p className="mt-4 rounded-xl bg-alert-light px-4 py-3 text-sm text-alert" role="alert">{error}</p>}

        {plan && (
          <div className="mt-6 space-y-5">
            {items.length === 0 ? (
              <p className="rounded-2xl bg-mist px-4 py-4 text-[15px] text-slate">{plan.explanation[plan.explanation.length - 1]}</p>
            ) : (
              <>
                <div>
                  <p className="text-sm font-semibold text-slate">Recommended {MEAL_TYPES.find((m) => m.value === plan.meal_type)?.label.toLowerCase()}</p>
                  <ul className="mt-2 divide-y divide-line rounded-2xl border border-line">
                    {items.map((i) => {
                      const g = Number(grams[i.container_id] || 0);
                      const n = scaled(i, g);
                      return (
                        <li key={i.container_id} className="flex flex-col gap-3 px-4 py-3.5 sm:flex-row sm:items-center">
                          <div className="min-w-0 flex-1">
                            <p className="font-semibold">{i.food_name} <span className="text-sm font-normal text-slate">· {i.container_label}</span></p>
                            <div className="mt-1"><CategoryTags categories={i.categories} /></div>
                            <p className="mt-1 text-xs text-slate">{i.reasons.join(" · ")}</p>
                          </div>
                          <div className="flex items-center gap-3 sm:flex-col sm:items-end">
                            <div className="flex items-center gap-1">
                              <Button size="icon" variant="secondary" onClick={() => adjust(i.container_id, -5)} aria-label={`Less ${i.food_name}`}><Minus className="h-4 w-4" /></Button>
                              <label className="relative">
                                <span className="sr-only">Grams of {i.food_name}</span>
                                <input type="number" min="0" max="500" value={grams[i.container_id]}
                                  onChange={(e) => setGrams((s) => ({ ...s, [i.container_id]: e.target.value }))}
                                  className="field-input num w-24 py-2 pr-7 text-center font-semibold" />
                                <span className="pointer-events-none absolute inset-y-0 right-2.5 flex items-center text-sm text-slate">g</span>
                              </label>
                              <Button size="icon" variant="secondary" onClick={() => adjust(i.container_id, 5)} aria-label={`More ${i.food_name}`}><Plus className="h-4 w-4" /></Button>
                            </div>
                            <p className="num text-xs text-slate">≈ {Math.round(n.kcal)} kcal · P {n.protein.toFixed(1)} · C {n.carbs.toFixed(1)} · F {n.fat.toFixed(1)}</p>
                          </div>
                        </li>
                      );
                    })}
                  </ul>
                </div>

                <div>
                  <p className="mb-2 text-sm font-semibold text-slate">Estimated nutrition vs. this meal’s target</p>
                  <div className="grid gap-3 sm:grid-cols-4">
                    {MACROS.map(([k, label, unit, color]) => {
                      const pct = target?.[k] ? Math.min((totals[k] / target[k]) * 100, 130) : 0;
                      return (
                        <div key={k}>
                          <div className="mb-1 flex justify-between text-xs"><span className="font-semibold">{label}</span>
                            <span className="num text-slate">{Math.round(totals[k])} / {Math.round(target?.[k] || 0)} {unit}</span></div>
                          <div className="h-2 overflow-hidden rounded-full bg-mist"><div className="h-full rounded-full transition-[width]" style={{ width: `${Math.min(pct, 100)}%`, background: pct > 115 ? "#B4412F" : color }} /></div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                <details className="rounded-2xl bg-mist px-4 py-3 text-sm">
                  <summary className="flex cursor-pointer list-none items-center gap-2 font-semibold"><Info className="h-4 w-4 text-slate" aria-hidden />How this was worked out</summary>
                  <ul className="mt-2 space-y-1 text-slate">
                    {plan.explanation.map((e) => <li key={e}>• {e}</li>)}
                    {plan.skipped.map((e) => <li key={e} className="text-[#7A5A12]">• {e}</li>)}
                  </ul>
                </details>

                <Button size="lg" className="w-full sm:w-auto" icon={ChefHat} loading={busy === "serve"} disabled={!!disabledReason} onClick={serve}>
                  Serve Meal
                </Button>
                {disabledReason && <p className="text-sm text-slate">{disabledReason}</p>}
              </>
            )}
          </div>
        )}
        {!plan && !error && (
          <p className="mt-4 text-sm text-slate">Click <span className="font-semibold text-ink">Generate My Meal</span> to get portions from the foods in your containers. You can adjust them before serving.</p>
        )}
      </div>
    </section>
  );
}
