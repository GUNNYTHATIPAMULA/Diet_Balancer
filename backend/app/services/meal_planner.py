"""Deterministic meal planner: grams of each container food for one meal.

Every food contributes ALL its macronutrients (eggs give protein AND fat), so the
planner balances the whole meal, not just each food's primary category.

Objective (minimised by bounded coordinate descent; convex, so it converges):
    sum over k in {kcal, protein, carbs, fat} of  w_k * ((meal_k - target_k) / scale_k)^2
    with any overshoot (meal_k > target_k) weighted 3x, and a steep penalty if the meal's
    calories would exceed what's left for the whole day.
Then portions under a practical minimum are dropped, everything is rounded to 5 g, and
the meal is scaled down if it would still pass the day's remaining calories.
"""
from dataclasses import dataclass, field

MACROS = ("kcal", "protein", "carbs", "fat")
WEIGHTS = {"kcal": 1.0, "protein": 1.5, "carbs": 0.8, "fat": 0.8}
FLOORS = {"kcal": 150.0, "protein": 10.0, "carbs": 15.0, "fat": 5.0}  # scale for small targets
OVERSHOOT_FACTOR = 3.0
MIN_PORTION_G = 10.0
ROUND_TO_G = 5.0
NAMES = {"kcal": "calories", "protein": "protein", "carbs": "carbohydrates", "fat": "fat"}


@dataclass
class PlanFood:
    key: str               # container id
    name: str
    per100: dict           # kcal, protein, carbs, fat, fiber per 100 g (verified values)
    max_g: float


@dataclass
class PlannedItem:
    key: str
    name: str
    grams: float
    nutrition: dict
    reasons: list[str] = field(default_factory=list)


@dataclass
class PlanResult:
    items: list[PlannedItem]
    totals: dict
    meal_target: dict
    notes: list[str]


def nutrition_for(per100: dict, grams: float) -> dict:
    f = grams / 100.0
    return {k: round(per100.get(k, 0.0) * f, 1) for k in ("kcal", "protein", "carbs", "fat", "fiber")}


def _totals(foods: list[PlanFood], grams: list[float]) -> dict:
    t = {k: 0.0 for k in ("kcal", "protein", "carbs", "fat", "fiber")}
    for food, g in zip(foods, grams):
        for k in t:
            t[k] += food.per100.get(k, 0.0) * g / 100.0
    return t


def _objective(foods, grams, target, day_kcal_left) -> float:
    t = _totals(foods, grams)
    j = 0.0
    for k in MACROS:
        d = (t[k] - target[k]) / max(target[k], FLOORS[k])
        j += WEIGHTS[k] * d * d * (OVERSHOOT_FACTOR if d > 0 else 1.0)
    excess = t["kcal"] - day_kcal_left
    if excess > 0:
        j += 50.0 * (excess / max(day_kcal_left, FLOORS["kcal"])) ** 2
    return j + 1e-7 * sum(g * g for g in grams)


def _optimise(foods, target, day_kcal_left, sweeps: int = 60) -> list[float]:
    grams = [0.0] * len(foods)
    for _ in range(sweeps):
        moved = 0.0
        for i, food in enumerate(foods):
            lo, hi = 0.0, food.max_g
            for _ in range(40):  # golden-section search on one coordinate (objective is convex in it)
                m1 = lo + (hi - lo) * 0.382
                m2 = lo + (hi - lo) * 0.618
                g1, g2 = list(grams), list(grams)
                g1[i], g2[i] = m1, m2
                if _objective(foods, g1, target, day_kcal_left) <= _objective(foods, g2, target, day_kcal_left):
                    hi = m2
                else:
                    lo = m1
            new = (lo + hi) / 2
            moved = max(moved, abs(new - grams[i]))
            grams[i] = new
        if moved < 0.05:
            break
    return grams


def plan_meal(foods: list[PlanFood], meal_target: dict, day_remaining: dict) -> PlanResult:
    notes: list[str] = []
    target = {k: max(meal_target.get(k, 0.0), 0.0) for k in MACROS}
    day_kcal_left = max(day_remaining.get("kcal", 0.0), 0.0)
    if not foods:
        return PlanResult([], _totals([], []), target, ["No containers with a usable food."])
    if target["kcal"] < 50 or day_kcal_left < 50:
        return PlanResult([], _totals([], []), target,
                          ["You have already reached today's calorie target, so no meal is suggested."])

    active = list(foods)
    while True:
        grams = _optimise(active, target, day_kcal_left)
        small = [i for i, g in enumerate(grams) if g < MIN_PORTION_G]
        if not small or len(small) == len(active):
            break
        for i in sorted(small, reverse=True):
            notes.append(f"{active[i].name} left out: less than {MIN_PORTION_G:g} g would help this meal.")
            active.pop(i)

    grams = [max(round(g / ROUND_TO_G) * ROUND_TO_G, 0.0) if g >= MIN_PORTION_G else 0.0 for g in grams]
    total = _totals(active, grams)
    if total["kcal"] > day_kcal_left > 0:  # never plan past the day's remaining calories
        factor = day_kcal_left / total["kcal"]
        grams = [max(int(g * factor / ROUND_TO_G) * ROUND_TO_G, 0.0) for g in grams]
        notes.append("Portions were reduced to stay within today's remaining calories.")
    items = []
    for food, g in zip(active, grams):
        if g < MIN_PORTION_G:
            continue
        n = nutrition_for(food.per100, g)
        reasons = []
        for k in ("protein", "carbs", "fat"):
            if target[k] >= 1 and n[k] >= 0.15 * target[k]:
                reasons.append(f"{n[k]:g} g {NAMES[k]} ({min(n[k] / target[k], 9.99):.0%} of this meal's {NAMES[k]})")
        if n["fiber"] >= 3:
            reasons.append(f"{n['fiber']:g} g fiber")
        items.append(PlannedItem(key=food.key, name=food.name, grams=g, nutrition=n, reasons=reasons))
    totals = _totals([f for f in active if any(i.key == f.key for i in items)], [i.grams for i in items])
    return PlanResult(items=items, totals={k: round(v, 1) for k, v in totals.items()}, meal_target=target, notes=notes)
