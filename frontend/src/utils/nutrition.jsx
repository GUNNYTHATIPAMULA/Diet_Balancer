import { Droplets, Egg, Leaf, Shapes, Wheat } from "lucide-react";
import { API_BASE_URL } from "../api/client";

export const CATEGORY = {
  protein: { label: "Protein", cls: "bg-river-light text-river", tint: "from-river-light to-white text-river", icon: Egg },
  carbohydrates: { label: "Carbohydrates", short: "Carbs", cls: "bg-wheat-light text-[#7A5A12]", tint: "from-wheat-light to-white text-wheat", icon: Wheat },
  fat: { label: "Fat", cls: "bg-beet-light text-beet", tint: "from-beet-light to-white text-beet", icon: Droplets },
  fiber: { label: "Fiber", cls: "bg-sprout-light text-canopy", tint: "from-sprout-light to-white text-canopy", icon: Leaf },
  mixed: { label: "Mixed nutrition", short: "Mixed", cls: "bg-mist text-slate ring-1 ring-line", tint: "from-mist to-white text-slate", icon: Shapes },
};

export function CategoryTags({ categories = [], size = "sm" }) {
  if (!categories.length) return null;
  return (
    <ul className="flex flex-wrap gap-1.5" aria-label="Nutrition categories">
      {categories.map((c, i) => {
        const meta = CATEGORY[c] || CATEGORY.mixed;
        const Icon = meta.icon;
        return (
          <li key={c} className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 font-semibold ${meta.cls} ${size === "sm" ? "text-xs" : "text-sm"}`}>
            <Icon className="h-3 w-3" aria-hidden />
            {meta.short || meta.label}
            {i === 0 && categories.length > 1 && <span className="sr-only"> (main)</span>}
          </li>
        );
      })}
    </ul>
  );
}

/** Absolute URL for media paths the API returns (e.g. /api/v1/media/containers/…). */
export function mediaUrl(path) {
  if (!path) return null;
  try { return new URL(path, API_BASE_URL).toString(); } catch { return path; }
}

const ACCURACY = {
  within_tolerance: ["On target", "bg-sprout-light text-canopy"],
  over: ["Over target", "bg-wheat-light text-[#7A5A12]"],
  under: ["Under target", "bg-wheat-light text-[#7A5A12]"],
};

export function AccuracyBadge({ command }) {
  if (!command?.accuracy) return null;
  const [label, cls] = ACCURACY[command.accuracy];
  const d = command.difference_g;
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${cls}`}
      title={`Tolerance ±${command.tolerance_percent}% (${command.tolerance_g} g)`}>
      {label}{command.accuracy !== "within_tolerance" && d != null ? ` ${d > 0 ? "+" : ""}${d} g (${command.difference_percent > 0 ? "+" : ""}${command.difference_percent}%)` : ""}
    </span>
  );
}

export function MacroLine({ n, className = "" }) {
  if (!n) return null;
  const kcal = n.kcal ?? n.calories;
  const p = n.protein ?? n.protein_g;
  const c = n.carbs ?? n.carbs_g;
  const f = n.fat ?? n.fat_g;
  return (
    <p className={`num text-xs text-slate ${className}`}>
      <span className="font-semibold text-ink">{Math.round(kcal)} kcal</span> · P {Number(p).toFixed(1)} · C {Number(c).toFixed(1)} · F {Number(f).toFixed(1)} g
    </p>
  );
}

export function defaultMealType(date = new Date()) {
  const h = date.getHours();
  return h < 11 ? "breakfast" : h < 16 ? "lunch" : h < 22 ? "dinner" : "snacks";
}
