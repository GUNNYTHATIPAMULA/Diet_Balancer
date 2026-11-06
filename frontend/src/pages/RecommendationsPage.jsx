import { useState } from "react";
import { Lightbulb, Plus, ShieldCheck } from "lucide-react";
import { nutritionApi } from "../api/nutrition";
import { errorMessage } from "../api/client";
import { useAsync } from "../hooks/useAsync";
import { todayISO } from "../utils/format";
import { PageHeader } from "../components/PageHeader";
import { AddMealModal } from "../components/AddMealModal";
import { Button } from "../components/ui/Button";
import { Badge, EmptyState, ErrorState, PageSkeleton } from "../components/ui/Feedback";

const FOCUS = { protein: ["blue", "Protein first"], carbohydrates: ["amber", "Carbohydrates first"], fat: ["plum", "Healthy fats first"], balanced: ["green", "Balanced"], light: ["neutral", "Light options"] };

function asFood(r) {
  const k = 100 / r.suggested_quantity_g;
  return { id: r.food_id, name: r.food_name, calories_per_100g: r.calories * k, protein_per_100g: r.protein_g * k, carbs_per_100g: r.carbs_g * k, fat_per_100g: r.fat_g * k, serving_unit: r.serving_hint, serving_size_g: r.suggested_quantity_g };
}

export default function RecommendationsPage() {
  const today = todayISO();
  const { data, error, loading, reload } = useAsync(() => nutritionApi.recommendations(today, 12), [today]);
  const [adding, setAdding] = useState(null);

  if (loading && !data) return <PageSkeleton />;
  if (error && !data) return <ErrorState message={errorMessage(error)} onRetry={reload} />;
  const [tone, label] = FOCUS[data.focus] || FOCUS.balanced;

  return (
    <div>
      <PageHeader title="Recommendations" subtitle="Suggestions ranked by what’s left in today’s targets, filtered by your preferences and allergies." />
      <section className="panel mb-6 flex flex-col gap-4 p-6 sm:flex-row sm:items-center">
        <div className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-wheat-light text-wheat"><Lightbulb className="h-6 w-6" aria-hidden /></div>
        <div className="flex-1">
          <Badge tone={tone}>{label}</Badge>
          <p className="mt-2 text-[15px] text-ink">{data.message}</p>
          {data.remaining && (
            <p className="num mt-1 text-sm text-slate">
              Left today: {Math.round(data.remaining.calories)} kcal · {Math.round(data.remaining.protein_g)} g protein · {Math.round(data.remaining.carbs_g)} g carbs · {Math.round(data.remaining.fat_g)} g fat
            </p>
          )}
        </div>
        {data.excluded_count > 0 && (
          <p className="flex items-center gap-1.5 text-sm text-slate"><ShieldCheck className="h-4 w-4 text-leaf" aria-hidden />{data.excluded_count} foods hidden for your diet or allergies</p>
        )}
      </section>

      {data.items.length === 0 ? (
        <div className="panel"><EmptyState icon={Lightbulb} title="No matching suggestions">Your preferences and restrictions exclude every food in the library. Add custom foods in the Food Tracker.</EmptyState></div>
      ) : (
        <ul className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {data.items.map((r) => (
            <li key={r.food_id} className="panel flex flex-col p-5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="font-sans text-[17px] font-semibold">{r.food_name}</h2>
                  <p className="text-sm text-slate">{r.category}</p>
                </div>
                <span className="num rounded-xl bg-mist px-2.5 py-1 text-sm font-semibold">{r.suggested_quantity_g} g</span>
              </div>
              <dl className="num mt-4 grid grid-cols-4 gap-1 text-center">
                {[["kcal", Math.round(r.calories), "text-canopy"], ["P", r.protein_g, "text-river"], ["C", r.carbs_g, "text-wheat"], ["F", r.fat_g, "text-beet"]].map(([k, v, c]) => (
                  <div key={k} className="rounded-xl bg-mist py-2"><dd className={`font-display text-lg font-semibold ${c}`}>{v}</dd><dt className="text-xs text-slate">{k === "kcal" ? "kcal" : `g ${k === "P" ? "protein" : k === "C" ? "carbs" : "fat"}`}</dt></div>
                ))}
              </dl>
              <ul className="mt-4 flex-1 space-y-1.5 text-sm text-slate">
                {r.reasons.map((reason) => <li key={reason} className="flex gap-2"><span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-leaf" aria-hidden />{reason}</li>)}
              </ul>
              <div className="mt-4 flex items-center justify-between gap-2">
                <span className="text-xs text-slate-light">{r.serving_hint}{r.is_approximate ? " · approx. values" : ""}</span>
                <Button size="sm" variant="soft" icon={Plus} onClick={() => setAdding(r)}>Log</Button>
              </div>
            </li>
          ))}
        </ul>
      )}
      <p className="mt-6 text-sm text-slate">Suggestions come from transparent rules ({data.engine}), not a medical assessment.</p>
      <AddMealModal open={!!adding} day={today} defaultMeal="snacks" initialFood={adding ? asFood(adding) : null} initialGrams={adding?.suggested_quantity_g}
        onClose={() => setAdding(null)} onSaved={() => reload({ silent: true })} />
    </div>
  );
}
