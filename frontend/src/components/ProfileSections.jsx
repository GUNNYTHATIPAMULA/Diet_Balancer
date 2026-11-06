import { useState } from "react";
import { X } from "lucide-react";
import { ACTIVITY_LEVELS, ALLERGENS, DIET_PREFERENCES, GOALS, PACES } from "../utils/constants";
import { Input } from "./ui/Field";
import { ChoiceCards } from "./ui/Segmented";

export const EMPTY_PROFILE = {
  age: "", sex: "", height_cm: "", weight_kg: "", activity_level: "", goal_type: "maintain", goal_pace: "gentle",
  target_weight_kg: "", dietary_preference: "none", allergies: [], restrictions: [], meals_per_day: 3,
};

export function profileToForm(p) {
  return { ...EMPTY_PROFILE, ...p, target_weight_kg: p.target_weight_kg ?? "" };
}

export function formToPayload(f) {
  return {
    age: Number(f.age), sex: f.sex, height_cm: Number(f.height_cm), weight_kg: Number(f.weight_kg),
    activity_level: f.activity_level, goal_type: f.goal_type, goal_pace: f.goal_pace,
    target_weight_kg: f.goal_type !== "maintain" && f.target_weight_kg !== "" ? Number(f.target_weight_kg) : null,
    dietary_preference: f.dietary_preference, allergies: f.allergies, restrictions: f.restrictions,
    meals_per_day: Number(f.meals_per_day),
  };
}

export function validateBody(f) {
  const e = {};
  const age = Number(f.age), h = Number(f.height_cm), w = Number(f.weight_kg);
  if (!f.age || age < 18 || age > 100) e.age = "Enter an age between 18 and 100. Estimates here are designed for adults.";
  if (!f.sex) e.sex = "Choose the equation to use.";
  if (!f.height_cm || h < 120 || h > 230) e.height_cm = "Enter a height between 120 and 230 cm.";
  if (!f.weight_kg || w < 30 || w > 300) e.weight_kg = "Enter a weight between 30 and 300 kg.";
  return e;
}

export function validateGoal(f) {
  const e = {};
  if (!f.activity_level) e.activity_level = "Choose your activity level.";
  const t = Number(f.target_weight_kg), w = Number(f.weight_kg);
  if (f.goal_type !== "maintain" && f.target_weight_kg !== "") {
    if (t < 30 || t > 300) e.target_weight_kg = "Enter a target between 30 and 300 kg.";
    else if (f.goal_type === "lose" && t >= w) e.target_weight_kg = "For weight loss, the target must be below your current weight.";
    else if (f.goal_type === "gain" && t <= w) e.target_weight_kg = "For weight gain, the target must be above your current weight.";
  }
  return e;
}

export function BodySection({ form, set, errors }) {
  return (
    <div className="space-y-5">
      <div className="grid gap-4 sm:grid-cols-3">
        <Input label="Age" type="number" inputMode="numeric" suffix="yrs" value={form.age} onChange={(e) => set("age", e.target.value)} error={errors.age} />
        <Input label="Height" type="number" inputMode="decimal" suffix="cm" value={form.height_cm} onChange={(e) => set("height_cm", e.target.value)} error={errors.height_cm} />
        <Input label="Weight" type="number" inputMode="decimal" step="0.1" suffix="kg" value={form.weight_kg} onChange={(e) => set("weight_kg", e.target.value)} error={errors.weight_kg} />
      </div>
      <div>
        <p className="mb-1 text-sm font-semibold text-ink">Sex for the calorie equation</p>
        <p className="mb-3 text-sm text-slate">The Mifflin-St Jeor formula has two versions. Choose the one that best matches your body; they differ by 166 kcal.</p>
        <ChoiceCards name="Equation" value={form.sex} onChange={(v) => set("sex", v)} options={[
          { value: "female", label: "Female equation", hint: "… − 5 × age − 161" },
          { value: "male", label: "Male equation", hint: "… − 5 × age + 5" },
        ]} />
        {errors.sex && <p className="mt-2 text-sm text-alert">{errors.sex}</p>}
      </div>
    </div>
  );
}

export function GoalSection({ form, set, errors }) {
  return (
    <div className="space-y-6">
      <div>
        <p className="mb-3 text-sm font-semibold text-ink">How active are you on a typical week?</p>
        <ChoiceCards name="Activity level" value={form.activity_level} onChange={(v) => set("activity_level", v)}
          options={ACTIVITY_LEVELS.map((a) => ({ ...a, hint: `${a.hint} · ×${a.factor}` }))} />
        {errors.activity_level && <p className="mt-2 text-sm text-alert">{errors.activity_level}</p>}
      </div>
      <div>
        <p className="mb-3 text-sm font-semibold text-ink">What’s your goal?</p>
        <ChoiceCards name="Goal" columns="sm:grid-cols-3" value={form.goal_type} onChange={(v) => set("goal_type", v)} options={GOALS} />
      </div>
      {form.goal_type !== "maintain" && (
        <div className="grid gap-5 sm:grid-cols-[1fr_200px]">
          <div>
            <p className="mb-3 text-sm font-semibold text-ink">Pace</p>
            <ChoiceCards name="Pace" value={form.goal_pace} onChange={(v) => set("goal_pace", v)} options={PACES} />
          </div>
          <Input label="Target weight (optional)" type="number" step="0.1" suffix="kg" value={form.target_weight_kg}
            onChange={(e) => set("target_weight_kg", e.target.value)} error={errors.target_weight_kg} />
        </div>
      )}
    </div>
  );
}

export function PreferenceSection({ form, set }) {
  const [draft, setDraft] = useState("");
  const addRestriction = () => {
    const v = draft.trim().toLowerCase();
    if (v && !form.restrictions.includes(v) && form.restrictions.length < 20) set("restrictions", [...form.restrictions, v]);
    setDraft("");
  };
  return (
    <div className="space-y-6">
      <div>
        <p className="mb-3 text-sm font-semibold text-ink">Dietary preference</p>
        <ChoiceCards name="Dietary preference" columns="grid-cols-2 sm:grid-cols-3" value={form.dietary_preference}
          onChange={(v) => set("dietary_preference", v)} options={DIET_PREFERENCES} />
      </div>
      <div>
        <p className="mb-1 text-sm font-semibold text-ink">Allergies</p>
        <p className="mb-3 text-sm text-slate">Foods containing these are never recommended.</p>
        <ChoiceCards name="Allergies" multiple columns="grid-cols-2 sm:grid-cols-3" value={form.allergies}
          onChange={(v) => set("allergies", v)} options={ALLERGENS} />
      </div>
      <div>
        <p className="mb-1 text-sm font-semibold text-ink">Foods to avoid</p>
        <p className="mb-3 text-sm text-slate">Words like “rice” or “fried”. Any food whose name or category contains one is left out of suggestions.</p>
        <div className="flex gap-2">
          <input className="field-input" value={draft} maxLength={40} placeholder="e.g. potato" aria-label="Food to avoid"
            onChange={(e) => setDraft(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addRestriction(); } }} />
          <button type="button" onClick={addRestriction} className="shrink-0 rounded-xl bg-sprout-light px-4 text-sm font-semibold text-canopy hover:bg-sprout">Add</button>
        </div>
        {form.restrictions.length > 0 && (
          <ul className="mt-3 flex flex-wrap gap-2">
            {form.restrictions.map((r) => (
              <li key={r} className="inline-flex items-center gap-1 rounded-full bg-mist py-1 pl-3 pr-1.5 text-sm ring-1 ring-line">
                {r}
                <button type="button" onClick={() => set("restrictions", form.restrictions.filter((x) => x !== r))} className="rounded-full p-0.5 text-slate hover:text-alert" aria-label={`Remove ${r}`}><X className="h-3.5 w-3.5" /></button>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="max-w-[220px]">
        <Input label="Meals per day" type="number" min="1" max="8" value={form.meals_per_day} onChange={(e) => set("meals_per_day", e.target.value)}
          hint="Used to size suggested portions." />
      </div>
    </div>
  );
}
