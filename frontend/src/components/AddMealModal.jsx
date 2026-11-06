import { useEffect, useState } from "react";
import { mealsApi } from "../api/meals";
import { errorMessage, fieldErrors } from "../api/client";
import { MEAL_TYPES } from "../utils/constants";
import { useToast } from "../context/ToastContext";
import { Modal } from "./ui/Modal";
import { Button } from "./ui/Button";
import { Input, Select } from "./ui/Field";
import { FoodPicker } from "./FoodPicker";
import { Segmented } from "./ui/Segmented";

function preview(food, grams) {
  const f = Number(grams) / 100 || 0;
  return {
    calories: food.calories_per_100g * f,
    protein: food.protein_per_100g * f,
    carbs: food.carbs_per_100g * f,
    fat: food.fat_per_100g * f,
  };
}

/** Add a new entry (pick food) or edit an existing one (entry prop). */
export function AddMealModal({ open, onClose, onSaved, day, defaultMeal = "breakfast", entry = null, initialFood = null, initialGrams }) {
  const toast = useToast();
  const [food, setFood] = useState(null);
  const [grams, setGrams] = useState("");
  const [mealType, setMealType] = useState(defaultMeal);
  const [errors, setErrors] = useState({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    setErrors({});
    if (entry) {
      setFood({ id: entry.food_item_id, name: entry.food_name, calories_per_100g: entry.calories / entry.quantity_g * 100,
        protein_per_100g: entry.protein_g / entry.quantity_g * 100, carbs_per_100g: entry.carbs_g / entry.quantity_g * 100,
        fat_per_100g: entry.fat_g / entry.quantity_g * 100, serving_unit: "", serving_size_g: entry.quantity_g });
      setGrams(String(entry.quantity_g));
      setMealType(entry.meal_type);
    } else {
      setFood(initialFood);
      setGrams(initialGrams ? String(initialGrams) : initialFood ? String(initialFood.serving_size_g) : "");
      setMealType(defaultMeal);
    }
  }, [open, entry, defaultMeal, initialFood, initialGrams]);

  const pickFood = (f) => {
    setFood(f);
    setGrams(String(f.serving_size_g));
  };

  const measured = entry?.source === "dispenser";

  const save = async () => {
    const qty = Number(grams);
    if (!food) return setErrors({ food: "Choose a food first." });
    if (!qty || qty <= 0 || qty > 5000) return setErrors({ quantity_g: "Enter a quantity between 1 and 5000 grams." });
    setSaving(true);
    try {
      if (entry) {
        await mealsApi.update(entry.id, measured ? { meal_type: mealType } : { meal_type: mealType, quantity_g: qty });
        toast.success("Entry updated.");
      } else {
        await mealsApi.create({ food_item_id: food.id, meal_type: mealType, quantity_g: qty, consumed_on: day });
        toast.success(`${food.name} added to ${MEAL_TYPES.find((m) => m.value === mealType).label.toLowerCase()}.`);
      }
      onSaved?.();
      onClose();
    } catch (e) {
      setErrors(fieldErrors(e));
      toast.error(errorMessage(e));
    } finally {
      setSaving(false);
    }
  };

  const p = food ? preview(food, grams) : null;
  return (
    <Modal open={open} onClose={onClose} title={entry ? "Edit entry" : "Add food"}
      description={entry ? entry.food_name : "Search the food library, then enter the amount in grams."}
      footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button loading={saving} onClick={save}>{entry ? "Save changes" : "Add to log"}</Button></>}>
      <div className="space-y-5">
        {!entry && (
          <div>
            {food ? (
              <div className="flex items-center justify-between rounded-2xl bg-sprout-light px-4 py-3">
                <div>
                  <p className="font-semibold text-ink">{food.name}</p>
                  <p className="text-sm text-slate">{Math.round(food.calories_per_100g)} kcal per 100 g · {food.serving_unit} ≈ {food.serving_size_g} g</p>
                </div>
                <Button size="sm" variant="ghost" onClick={() => setFood(null)}>Change</Button>
              </div>
            ) : (
              <FoodPicker onSelect={pickFood} autoFocus />
            )}
            {errors.food && <p className="mt-2 text-sm text-alert">{errors.food}</p>}
          </div>
        )}
        <div className="grid gap-4 sm:grid-cols-2">
          <Input label="Quantity" type="number" inputMode="decimal" min="1" max="5000" step="1" suffix="g"
            value={grams} onChange={(e) => setGrams(e.target.value)} error={errors.quantity_g} disabled={measured}
            hint={measured ? "Measured by the dispenser's scale, so it can't be edited." : undefined} />
          <Select label="Meal" options={MEAL_TYPES} value={mealType} onChange={(e) => setMealType(e.target.value)} />
        </div>
        {p && (
          <div className="grid grid-cols-4 gap-2 rounded-2xl border border-line p-3 text-center">
            {[["kcal", p.calories, "text-canopy"], ["protein", p.protein, "text-river"], ["carbs", p.carbs, "text-wheat"], ["fat", p.fat, "text-beet"]].map(([label, v, color]) => (
              <div key={label}>
                <p className={`num font-display text-xl font-semibold ${color}`}>{label === "kcal" ? Math.round(v) : v.toFixed(1)}</p>
                <p className="text-xs text-slate">{label === "kcal" ? "kcal" : `g ${label}`}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </Modal>
  );
}

export function MealTypePicker({ value, onChange }) {
  return <Segmented label="Meal" size="sm" options={MEAL_TYPES} value={value} onChange={onChange} />;
}
