import { useEffect, useState } from "react";
import { Gauge, Settings2 } from "lucide-react";
import { MEAL_TYPES } from "../../utils/constants";
import { CATEGORY, CategoryTags, mediaUrl } from "../../utils/nutrition";
import { Button } from "../ui/Button";

function FoodVisual({ container }) {
  const primary = container.food?.categories?.[0];
  const meta = CATEGORY[primary] || CATEGORY.mixed;
  const Icon = meta.icon;
  const src = mediaUrl(container.image_url);
  if (src) return <img src={src} alt={container.food?.name || container.label} className="h-full w-full object-cover" />;
  return (
    <div className={`grid h-full w-full place-items-center bg-gradient-to-br ${container.food ? meta.tint : "from-mist to-white text-slate-light"}`}>
      <Icon className="h-10 w-10 opacity-80" aria-hidden />
    </div>
  );
}

/** One physical container: what's inside, its nutrition per 100 g, and a quick Serve. */
export function ContainerCard({ container, defaultMeal, disabledReason, busy, onServe, onConfigure }) {
  const food = container.food;
  const [grams, setGrams] = useState("");
  const [meal, setMeal] = useState(defaultMeal);
  const [error, setError] = useState("");
  useEffect(() => { if (food) setGrams(String(Math.round(Math.min(Math.max(food.serving_size_g, 20), 200)))); }, [food?.id]);
  useEffect(() => setMeal(defaultMeal), [defaultMeal]);

  const serve = () => {
    const g = Number(grams);
    if (!g || g < 5 || g > 500) return setError("Enter 5 to 500 g.");
    setError("");
    onServe(container, g, meal);
  };

  return (
    <article className="flex flex-col overflow-hidden rounded-3xl border border-line bg-white shadow-card">
      <div className="relative h-32">
        <FoodVisual container={container} />
        <span className="absolute left-3 top-3 rounded-full bg-white/90 px-2.5 py-1 text-xs font-semibold text-ink shadow-sm">
          {container.label} · servo {container.servo_channel}
        </span>
        <button onClick={() => onConfigure(container)} aria-label={`Configure ${container.label}`}
          className="absolute right-3 top-3 grid h-8 w-8 place-items-center rounded-full bg-white/90 text-slate shadow-sm hover:text-ink">
          <Settings2 className="h-4 w-4" />
        </button>
        {!container.is_enabled && <span className="absolute bottom-3 left-3 rounded-full bg-ink/80 px-2.5 py-1 text-xs font-semibold text-white">Disabled</span>}
      </div>

      <div className="flex flex-1 flex-col p-5">
        {food ? (
          <>
            <h3 className="font-sans text-lg font-semibold leading-snug">{food.name}</h3>
            <div className="mt-2"><CategoryTags categories={food.categories} /></div>
            <dl className="num mt-4 grid grid-cols-4 gap-1.5 text-center">
              {[["kcal", food.calories_per_100g, "text-canopy"], ["protein", food.protein_per_100g, "text-river"],
                ["carbs", food.carbs_per_100g, "text-wheat"], ["fat", food.fat_per_100g, "text-beet"]].map(([k, v, cls]) => (
                <div key={k} className="rounded-xl bg-mist py-2">
                  <dd className={`font-display text-base font-semibold ${cls}`}>{k === "kcal" ? Math.round(v) : Number(v).toFixed(1)}</dd>
                  <dt className="text-[11px] text-slate">{k === "kcal" ? "kcal" : `g ${k}`}</dt>
                </div>
              ))}
            </dl>
            <p className="mt-1.5 text-center text-[11px] text-slate-light">per 100 g{food.is_approximate ? " · reference values" : " · verified source"}</p>

            <div className="mt-4 grid grid-cols-[1fr_1fr] gap-2">
              <label className="block">
                <span className="mb-1 block text-xs font-semibold text-slate">Amount</span>
                <div className="relative">
                  <input type="number" inputMode="decimal" min="5" max="500" value={grams} onChange={(e) => setGrams(e.target.value)}
                    className="field-input pr-8" aria-label={`Grams of ${food.name}`} aria-invalid={error ? "true" : undefined} />
                  <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-sm text-slate">g</span>
                </div>
              </label>
              <label className="block">
                <span className="mb-1 block text-xs font-semibold text-slate">Log under</span>
                <select value={meal} onChange={(e) => setMeal(e.target.value)} className="field-input" aria-label={`Meal for ${food.name}`}>
                  {MEAL_TYPES.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
                </select>
              </label>
            </div>
            {error && <p className="mt-2 text-sm text-alert" role="alert">{error}</p>}
            <Button className="mt-3" icon={Gauge} loading={busy} disabled={!!disabledReason || !container.is_enabled}
              onClick={serve} aria-label={`Serve ${food.name}`}>Serve</Button>
            {disabledReason && <p className="mt-2 text-xs text-slate">{disabledReason}</p>}
            {container.learned_inflight_g != null && (
              <p className="mt-2 text-[11px] text-slate-light">Learned: closes {container.learned_inflight_g} g early for this food.</p>
            )}
          </>
        ) : (
          <div className="flex flex-1 flex-col items-start">
            <h3 className="font-sans text-lg font-semibold text-slate">Empty</h3>
            <p className="mt-1 text-sm text-slate">Tell us what food is inside and we’ll work out its nutrition.</p>
            <Button className="mt-4" variant="soft" icon={Settings2} onClick={() => onConfigure(container)}>Configure container</Button>
          </div>
        )}
      </div>
    </article>
  );
}
