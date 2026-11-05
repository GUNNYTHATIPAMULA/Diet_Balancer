"""Rule-based, explainable food recommendations.

The engine is behind a small interface (RecommendationEngine) so an AI-based
engine can be added later without touching the API layer: implement
`recommend(context)` and register it in ENGINES.
"""
from dataclasses import dataclass, field
from typing import Protocol

from app.models.enums import DietaryPreference, DietType
from app.models.food import FoodItem
from app.schemas.meal import NutritionTotals
from app.services.nutrition_calculator import Targets

ALLOWED_DIET_TYPES: dict[DietaryPreference, set[DietType]] = {
    DietaryPreference.vegan: {DietType.vegan},
    DietaryPreference.vegetarian: {DietType.vegan, DietType.vegetarian},
    DietaryPreference.eggetarian: {DietType.vegan, DietType.vegetarian, DietType.eggetarian},
    DietaryPreference.non_vegetarian: set(DietType),
    DietaryPreference.none: set(DietType),
}
EXCLUDED_CATEGORIES = {"Fats & oils"}  # cooking ingredients, not something to "eat more of"
MAX_PER_CATEGORY = 2


@dataclass
class RecommendationContext:
    targets: Targets | None
    consumed: NutritionTotals
    dietary_preference: DietaryPreference
    allergies: list[str]
    restrictions: list[str]
    meals_per_day: int
    meals_logged_today: int
    foods: list[FoodItem]
    limit: int = 8


@dataclass
class Recommendation:
    food: FoodItem
    quantity_g: float
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    score: float
    reasons: list[str] = field(default_factory=list)


@dataclass
class RecommendationResult:
    focus: str
    message: str
    remaining: NutritionTotals | None
    items: list[Recommendation]
    excluded_count: int


class RecommendationEngine(Protocol):
    name: str

    def recommend(self, context: RecommendationContext) -> RecommendationResult: ...


def violates_profile(food: FoodItem, ctx: RecommendationContext) -> bool:
    if food.diet_type not in ALLOWED_DIET_TYPES[ctx.dietary_preference]:
        return True
    if set(food.allergens or []) & set(ctx.allergies):
        return True
    haystack = f"{food.name} {food.category}".lower()
    return any(term and term in haystack for term in ctx.restrictions)


class RuleBasedEngine:
    name = "rule_based_v1"

    def recommend(self, ctx: RecommendationContext) -> RecommendationResult:
        allowed, excluded = [], 0
        for food in ctx.foods:
            if violates_profile(food, ctx):
                excluded += 1
            elif food.category not in EXCLUDED_CATEGORIES and "(dry)" not in food.name.lower():
                allowed.append(food)

        if ctx.targets is None:
            return self._rank(allowed, ctx, focus="balanced", budget=500.0, need=(0.33, 0.33, 0.33),
                              remaining=None, excluded=excluded,
                              message="Complete your profile to get suggestions matched to your calorie target.")

        t, c = ctx.targets, ctx.consumed
        remaining = NutritionTotals(
            calories=round(t.calorie_target - c.calories, 1),
            protein_g=round(max(t.protein_g - c.protein_g, 0), 1),
            carbs_g=round(max(t.carbs_g - c.carbs_g, 0), 1),
            fat_g=round(max(t.fat_g - c.fat_g, 0), 1),
            fiber_g=round(max(t.fiber_g - c.fiber_g, 0), 1),
        )
        if remaining.calories <= 50:
            light = [f for f in allowed if float(f.calories_per_100g) <= 60]
            return self._rank(light, ctx, focus="light", budget=80.0, need=(0.4, 0.4, 0.2), remaining=remaining,
                              excluded=excluded,
                              message="You've reached today's calorie target. If you're still hungry, "
                                      "these lighter options add little energy.")

        need_p = remaining.protein_g / t.protein_g if t.protein_g else 0
        need_c = remaining.carbs_g / t.carbs_g if t.carbs_g else 0
        need_f = remaining.fat_g / t.fat_g if t.fat_g else 0
        focus = "balanced"
        top = max(need_p, need_c, need_f)
        if top > 0 and top - min(need_p, need_c, need_f) > 0.15:
            focus = max([(need_p, "protein"), (need_c, "carbohydrates"), (need_f, "fat")], key=lambda x: x[0])[1]
        meals_left = max(ctx.meals_per_day - ctx.meals_logged_today, 1)
        budget = min(max(remaining.calories / meals_left, 120.0), remaining.calories)
        messages = {
            "protein": f"You still need about {remaining.protein_g:.0f} g of protein today, so protein-rich "
                       f"foods are ranked first.",
            "carbohydrates": f"Carbohydrates are furthest from target ({remaining.carbs_g:.0f} g left).",
            "fat": f"Healthy fats are furthest from target ({remaining.fat_g:.0f} g left).",
            "balanced": "Your macros are evenly balanced so far. These options keep it that way.",
        }
        return self._rank(allowed, ctx, focus=focus, budget=budget, need=(need_p, need_c, need_f),
                          remaining=remaining, excluded=excluded,
                          message=messages[focus] + f" Portions are sized to about {budget:.0f} kcal.")

    def _rank(self, foods, ctx, *, focus, budget, need, remaining, excluded, message) -> RecommendationResult:
        need_p, need_c, need_f = need
        scored: list[Recommendation] = []
        for food in foods:
            kcal = float(food.calories_per_100g)
            p, cb, ft, fb = (float(food.protein_per_100g), float(food.carbs_per_100g),
                             float(food.fat_per_100g), float(food.fiber_per_100g))
            macro_kcal = p * 4 + cb * 4 + ft * 9
            if kcal <= 0 or macro_kcal <= 0:
                continue
            p_share, c_share, f_share = p * 4 / macro_kcal, cb * 4 / macro_kcal, ft * 9 / macro_kcal
            score = 1.6 * need_p * p_share + need_c * c_share + need_f * f_share
            score += min(fb / kcal * 100, 6) * 0.03            # fiber per 100 kcal
            if focus == "protein":
                score += min(p / kcal * 100, 15) * 0.04        # protein density bonus

            quantity = float(food.serving_size_g)
            if kcal * quantity / 100 > budget:
                quantity = max(int(budget * 100 / kcal / 5) * 5, 5)  # round down: never exceed budget
            factor = quantity / 100
            rec = Recommendation(food=food, quantity_g=quantity, calories=round(kcal * factor, 1),
                                 protein_g=round(p * factor, 1), carbs_g=round(cb * factor, 1),
                                 fat_g=round(ft * factor, 1), score=round(score, 4))
            rec.reasons = self._reasons(rec, fb * factor, ctx, focus, remaining)
            scored.append(rec)

        scored.sort(key=lambda r: (-r.score, r.food.name))
        picked, per_category = [], {}
        for rec in scored:
            if per_category.get(rec.food.category, 0) >= MAX_PER_CATEGORY:
                continue
            per_category[rec.food.category] = per_category.get(rec.food.category, 0) + 1
            picked.append(rec)
            if len(picked) >= ctx.limit:
                break
        return RecommendationResult(focus=focus, message=message, remaining=remaining, items=picked,
                                    excluded_count=excluded)

    @staticmethod
    def _reasons(rec: Recommendation, fiber: float, ctx, focus, remaining) -> list[str]:
        reasons = []
        if focus == "protein" and rec.protein_g >= 5 and remaining is not None:
            reasons.append(f"{rec.protein_g:g} g protein toward the {remaining.protein_g:.0f} g you still need.")
        elif focus == "carbohydrates" and rec.carbs_g >= 10:
            reasons.append(f"{rec.carbs_g:g} g carbohydrates for energy.")
        elif focus == "fat" and rec.fat_g >= 4:
            reasons.append(f"{rec.fat_g:g} g fat, mostly from whole foods.")
        if remaining is not None and focus != "light":
            reasons.append(f"{rec.calories:.0f} kcal fits within the {remaining.calories:.0f} kcal left today.")
        elif focus == "light":
            reasons.append(f"Only {rec.calories:.0f} kcal for this portion.")
        if fiber >= 3:
            reasons.append(f"{fiber:.1f} g fiber helps you feel full.")
        if ctx.dietary_preference != DietaryPreference.none:
            reasons.append(f"Fits your {ctx.dietary_preference.value.replace('_', '-')} preference.")
        if ctx.allergies:
            reasons.append("Free of your listed allergens.")
        return reasons


ENGINES: dict[str, RecommendationEngine] = {RuleBasedEngine.name: RuleBasedEngine()}
DEFAULT_ENGINE = RuleBasedEngine.name
