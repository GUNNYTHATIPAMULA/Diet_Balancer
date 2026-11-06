import { Coffee, Sun, Moon, Cookie, Pencil, Trash2, Plus, Cpu } from "lucide-react";
import { mealLabel } from "../utils/constants";
import { Badge } from "./ui/Feedback";

const ICONS = { breakfast: Coffee, lunch: Sun, dinner: Moon, snacks: Cookie };

export function MealSection({ group, onAdd, onEdit, onDelete, compact = false }) {
  const Icon = ICONS[group.meal_type];
  return (
    <section className="rounded-2xl border border-line/80 bg-white" aria-labelledby={`meal-${group.meal_type}`}>
      <div className="flex items-center justify-between gap-3 px-4 py-3">
        <div className="flex items-center gap-3">
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-sprout-light text-canopy"><Icon className="h-[18px] w-[18px]" aria-hidden /></span>
          <div>
            <h3 id={`meal-${group.meal_type}`} className="font-sans text-[15px] font-semibold">{mealLabel(group.meal_type)}</h3>
            <p className="num text-xs text-slate">
              {group.entries.length ? `${Math.round(group.totals.calories)} kcal · P ${group.totals.protein_g.toFixed(0)} · C ${group.totals.carbs_g.toFixed(0)} · F ${group.totals.fat_g.toFixed(0)}` : "Nothing logged"}
            </p>
          </div>
        </div>
        {onAdd && (
          <button onClick={() => onAdd(group.meal_type)} className="inline-flex items-center gap-1 rounded-xl px-2.5 py-1.5 text-sm font-semibold text-canopy hover:bg-sprout-light">
            <Plus className="h-4 w-4" aria-hidden /> Add
          </button>
        )}
      </div>
      {group.entries.length > 0 && (
        <ul className="divide-y divide-line/70 border-t border-line/70">
          {group.entries.map((e) => (
            <li key={e.id} className="flex items-center gap-3 px-4 py-2.5">
              <div className="min-w-0 flex-1">
                <p className="truncate text-[15px] text-ink">
                  {e.food_name}
                  {e.source === "dispenser" && <Badge tone="green" className="ml-2 align-middle"><Cpu className="h-3 w-3" aria-hidden />Measured</Badge>}
                </p>
                {!compact && (
                  <p className="num text-xs text-slate">{e.quantity_g} g · P {e.protein_g.toFixed(1)} g · C {e.carbs_g.toFixed(1)} g · F {e.fat_g.toFixed(1)} g</p>
                )}
                {compact && <p className="num text-xs text-slate">{e.quantity_g} g</p>}
              </div>
              <span className="num shrink-0 text-sm font-semibold text-ink">{Math.round(e.calories)} kcal</span>
              {onEdit && (
                <div className="flex shrink-0">
                  <button onClick={() => onEdit(e)} className="rounded-lg p-1.5 text-slate hover:bg-mist hover:text-ink" aria-label={`Edit ${e.food_name}`}><Pencil className="h-4 w-4" /></button>
                  <button onClick={() => onDelete(e)} className="rounded-lg p-1.5 text-slate hover:bg-alert-light hover:text-alert" aria-label={`Delete ${e.food_name}`}><Trash2 className="h-4 w-4" /></button>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
