import { useState } from "react";
import { ChevronLeft, ChevronRight, Plus, Search, Trash2 } from "lucide-react";
import { mealsApi } from "../api/meals";
import { foodsApi } from "../api/foods";
import { errorMessage, fieldErrors } from "../api/client";
import { useAsync } from "../hooks/useAsync";
import { useDebounce } from "../hooks/useDebounce";
import { useToast } from "../context/ToastContext";
import { formatDay, shiftDate, todayISO } from "../utils/format";
import { ALLERGENS, DIET_TYPE_LABELS } from "../utils/constants";
import { PageHeader } from "../components/PageHeader";
import { MealSection } from "../components/MealSection";
import { AddMealModal } from "../components/AddMealModal";
import { Button } from "../components/ui/Button";
import { Input, Select } from "../components/ui/Field";
import { ConfirmDialog, Modal } from "../components/ui/Modal";
import { Segmented } from "../components/ui/Segmented";
import { Badge, EmptyState, ErrorState, Skeleton } from "../components/ui/Feedback";

function DailyLog() {
  const toast = useToast();
  const [day, setDay] = useState(todayISO());
  const { data, error, loading, reload } = useAsync(() => mealsApi.daily(day), [day]);
  const [modal, setModal] = useState({ open: false, meal: "breakfast", entry: null });
  const [deleting, setDeleting] = useState(null);
  const isToday = day === todayISO();

  const remove = async () => {
    try {
      await mealsApi.remove(deleting.id);
      toast.success(`${deleting.food_name} removed.`);
      setDeleting(null);
      reload({ silent: true });
    } catch (e) {
      toast.error(errorMessage(e));
    }
  };

  return (
    <div className="space-y-5">
      <div className="panel flex flex-col gap-4 p-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2">
          <Button variant="secondary" size="icon" onClick={() => setDay(shiftDate(day, -1))} aria-label="Previous day"><ChevronLeft className="h-4 w-4" /></Button>
          <label className="relative">
            <span className="sr-only">Choose date</span>
            <input type="date" value={day} max={todayISO()} onChange={(e) => e.target.value && setDay(e.target.value)} className="field-input w-auto py-2" />
          </label>
          <Button variant="secondary" size="icon" disabled={isToday} onClick={() => setDay(shiftDate(day, 1))} aria-label="Next day"><ChevronRight className="h-4 w-4" /></Button>
          {!isToday && <Button variant="ghost" size="sm" onClick={() => setDay(todayISO())}>Today</Button>}
        </div>
        {data && (
          <dl className="num flex gap-5 text-sm">
            {[["kcal", data.totals.calories, 0], ["Protein", data.totals.protein_g, 1], ["Carbs", data.totals.carbs_g, 1], ["Fat", data.totals.fat_g, 1]].map(([label, v, d]) => (
              <div key={label}><dt className="text-slate">{label}</dt><dd className="font-display text-lg font-semibold">{v.toFixed(d)}{label !== "kcal" && " g"}</dd></div>
            ))}
          </dl>
        )}
      </div>
      <p className="font-display text-xl font-semibold">{formatDay(day)}</p>
      {loading && !data ? (
        <div className="space-y-3">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-20" />)}</div>
      ) : error ? (
        <ErrorState message={errorMessage(error)} onRetry={reload} />
      ) : (
        <div className="grid gap-3 lg:grid-cols-2">
          {data.meals.map((g) => (
            <MealSection key={g.meal_type} group={g} onAdd={(meal) => setModal({ open: true, meal, entry: null })}
              onEdit={(entry) => setModal({ open: true, meal: entry.meal_type, entry })} onDelete={setDeleting} />
          ))}
        </div>
      )}
      <AddMealModal open={modal.open} day={day} defaultMeal={modal.meal} entry={modal.entry}
        onClose={() => setModal((m) => ({ ...m, open: false }))} onSaved={() => reload({ silent: true })} />
      <ConfirmDialog open={!!deleting} title="Remove this entry?" confirmLabel="Remove"
        message={deleting ? `${deleting.food_name} (${deleting.quantity_g} g) will be removed from this day.` : ""}
        onConfirm={remove} onCancel={() => setDeleting(null)} />
    </div>
  );
}

const EMPTY_FOOD = { name: "", category: "", calories_per_100g: "", protein_per_100g: "", carbs_per_100g: "", fat_per_100g: "", fiber_per_100g: "0", serving_unit: "100 g", serving_size_g: "100", diet_type: "vegetarian", allergens: [] };

function CustomFoodModal({ open, onClose, onSaved }) {
  const toast = useToast();
  const [form, setForm] = useState(EMPTY_FOOD);
  const [errors, setErrors] = useState({});
  const [saving, setSaving] = useState(false);
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const numeric = ["calories_per_100g", "protein_per_100g", "carbs_per_100g", "fat_per_100g", "fiber_per_100g", "serving_size_g"];

  const save = async () => {
    const e = {};
    if (form.name.trim().length < 2) e.name = "Enter a name.";
    if (form.category.trim().length < 2) e.category = "Enter a category.";
    numeric.forEach((k) => { if (form[k] === "" || Number(form[k]) < 0) e[k] = "Required"; });
    if (Object.keys(e).length) return setErrors(e);
    setSaving(true);
    try {
      const body = { ...form, ...Object.fromEntries(numeric.map((k) => [k, Number(form[k])])) };
      const food = await foodsApi.create(body);
      toast.success(`${food.name} added to your food library.`);
      setForm(EMPTY_FOOD);
      onSaved();
      onClose();
    } catch (err) {
      setErrors(fieldErrors(err));
      toast.error(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose} size="lg" title="Add a custom food"
      description="Use values per 100 g from the package label or a trusted source. Only you can see custom foods."
      footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button loading={saving} onClick={save}>Save food</Button></>}>
      <div className="grid gap-4 sm:grid-cols-2">
        <Input label="Name" value={form.name} onChange={(e) => set("name", e.target.value)} error={errors.name} />
        <Input label="Category" value={form.category} placeholder="e.g. Breakfast" onChange={(e) => set("category", e.target.value)} error={errors.category} />
        <Input label="Calories per 100 g" type="number" suffix="kcal" value={form.calories_per_100g} onChange={(e) => set("calories_per_100g", e.target.value)} error={errors.calories_per_100g} />
        <Input label="Protein per 100 g" type="number" suffix="g" value={form.protein_per_100g} onChange={(e) => set("protein_per_100g", e.target.value)} error={errors.protein_per_100g} />
        <Input label="Carbohydrates per 100 g" type="number" suffix="g" value={form.carbs_per_100g} onChange={(e) => set("carbs_per_100g", e.target.value)} error={errors.carbs_per_100g} />
        <Input label="Fat per 100 g" type="number" suffix="g" value={form.fat_per_100g} onChange={(e) => set("fat_per_100g", e.target.value)} error={errors.fat_per_100g} />
        <Input label="Fiber per 100 g" type="number" suffix="g" value={form.fiber_per_100g} onChange={(e) => set("fiber_per_100g", e.target.value)} error={errors.fiber_per_100g} />
        <Select label="Diet type" value={form.diet_type} onChange={(e) => set("diet_type", e.target.value)}
          options={Object.entries(DIET_TYPE_LABELS).map(([value, label]) => ({ value, label }))} />
        <Input label="Serving name" value={form.serving_unit} onChange={(e) => set("serving_unit", e.target.value)} />
        <Input label="Serving size" type="number" suffix="g" value={form.serving_size_g} onChange={(e) => set("serving_size_g", e.target.value)} error={errors.serving_size_g} />
      </div>
      <fieldset className="mt-4">
        <legend className="mb-2 text-sm font-semibold">Contains allergens</legend>
        <div className="flex flex-wrap gap-2">
          {ALLERGENS.map((a) => {
            const on = form.allergens.includes(a.value);
            return (
              <button key={a.value} type="button" aria-pressed={on} onClick={() => set("allergens", on ? form.allergens.filter((x) => x !== a.value) : [...form.allergens, a.value])}
                className={`rounded-full px-3 py-1 text-sm font-medium ring-1 ${on ? "bg-sprout-light text-canopy ring-leaf" : "bg-white text-slate ring-line"}`}>{a.label}</button>
            );
          })}
        </div>
      </fieldset>
    </Modal>
  );
}

function FoodLibrary() {
  const toast = useToast();
  const [category, setCategory] = useState("");
  const [query, setQuery] = useState("");
  const q = useDebounce(query.trim(), 250);
  const cats = useAsync(() => foodsApi.categories(), []);
  const foods = useAsync(() => (q ? foodsApi.search(q, 50) : foodsApi.list({ category: category || undefined, limit: 200 })), [q, category]);
  const [adding, setAdding] = useState(null);
  const [custom, setCustom] = useState(false);
  const [removing, setRemoving] = useState(null);

  const remove = async () => {
    try {
      await foodsApi.remove(removing.id);
      toast.success(`${removing.name} deleted.`);
      setRemoving(null);
      foods.reload({ silent: true });
    } catch (e) {
      toast.error(errorMessage(e));
      setRemoving(null);
    }
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 sm:flex-row">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate" aria-hidden />
          <input className="field-input pl-10" placeholder="Search foods" value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Search foods" />
        </div>
        <Button variant="secondary" icon={Plus} onClick={() => setCustom(true)}>Custom food</Button>
      </div>
      {!q && cats.data && (
        <div className="flex flex-wrap gap-2" role="group" aria-label="Filter by category">
          {["", ...cats.data].map((c) => (
            <button key={c || "all"} aria-pressed={category === c} onClick={() => setCategory(c)}
              className={`rounded-full px-3.5 py-1.5 text-sm font-semibold ring-1 transition-colors ${category === c ? "bg-canopy text-white ring-canopy" : "bg-white text-slate ring-line hover:text-ink"}`}>
              {c || "All"}
            </button>
          ))}
        </div>
      )}
      {foods.loading && !foods.data ? (
        <div className="space-y-2">{[0, 1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-16" />)}</div>
      ) : foods.error ? (
        <ErrorState message={errorMessage(foods.error)} onRetry={foods.reload} />
      ) : foods.data.items.length === 0 ? (
        <div className="panel"><EmptyState icon={Search} title="No foods found" action={<Button variant="soft" icon={Plus} onClick={() => setCustom(true)}>Add a custom food</Button>}>Try a different word, or add the food yourself from its package label.</EmptyState></div>
      ) : (
        <div className="panel overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-left text-sm">
              <thead className="bg-mist text-slate">
                <tr>
                  <th className="px-4 py-3 font-semibold">Food (per 100 g)</th>
                  <th className="px-3 py-3 text-right font-semibold">kcal</th>
                  <th className="px-3 py-3 text-right font-semibold">Protein</th>
                  <th className="px-3 py-3 text-right font-semibold">Carbs</th>
                  <th className="px-3 py-3 text-right font-semibold">Fat</th>
                  <th className="px-3 py-3 text-right font-semibold">Fiber</th>
                  <th className="px-4 py-3"><span className="sr-only">Actions</span></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {foods.data.items.map((f) => (
                  <tr key={f.id} className="hover:bg-mist/60">
                    <td className="px-4 py-3">
                      <p className="font-semibold text-ink">{f.name}</p>
                      <p className="mt-0.5 flex flex-wrap items-center gap-1.5 text-xs text-slate">
                        {f.category} · {f.serving_unit} ≈ {f.serving_size_g} g
                        {f.is_custom ? <Badge tone="blue">Custom</Badge> : f.is_approximate && <Badge tone="amber" className="cursor-help" ><span title={f.source}>Approximate</span></Badge>}
                      </p>
                    </td>
                    <td className="num px-3 py-3 text-right font-semibold">{Math.round(f.calories_per_100g)}</td>
                    <td className="num px-3 py-3 text-right">{f.protein_per_100g} g</td>
                    <td className="num px-3 py-3 text-right">{f.carbs_per_100g} g</td>
                    <td className="num px-3 py-3 text-right">{f.fat_per_100g} g</td>
                    <td className="num px-3 py-3 text-right">{f.fiber_per_100g} g</td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex justify-end gap-1">
                        <Button size="sm" variant="soft" onClick={() => setAdding(f)}>Add to log</Button>
                        {f.is_custom && <Button size="icon" variant="ghost" onClick={() => setRemoving(f)} aria-label={`Delete ${f.name}`}><Trash2 className="h-4 w-4" /></Button>}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="border-t border-line px-4 py-3 text-xs text-slate">
            Built-in values are approximate references from USDA FoodData Central and the Indian Food Composition Tables (IFCT 2017). Hover “Approximate” to see each source.
          </p>
        </div>
      )}
      <AddMealModal open={!!adding} initialFood={adding} day={todayISO()} defaultMeal="snacks" onClose={() => setAdding(null)} />
      <CustomFoodModal open={custom} onClose={() => setCustom(false)} onSaved={() => { foods.reload({ silent: true }); cats.reload({ silent: true }); }} />
      <ConfirmDialog open={!!removing} title="Delete this custom food?" confirmLabel="Delete" message={removing ? `${removing.name} will be removed from your library.` : ""} onConfirm={remove} onCancel={() => setRemoving(null)} />
    </div>
  );
}

export default function FoodTrackerPage() {
  const [tab, setTab] = useState("log");
  return (
    <div>
      <PageHeader title="Food Tracker" subtitle="Log what you eat by weight. Nutrition is calculated from the amount you enter."
        actions={<Segmented label="View" value={tab} onChange={setTab} options={[{ value: "log", label: "Daily log" }, { value: "library", label: "Food library" }]} />} />
      {tab === "log" ? <DailyLog /> : <FoodLibrary />}
    </div>
  );
}
