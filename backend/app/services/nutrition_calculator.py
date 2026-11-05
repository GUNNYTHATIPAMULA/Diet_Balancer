"""Pure, documented nutrition maths. No database access here, so it is easy to test.

All results are population-level *estimates*. They are not medical advice.
"""
from dataclasses import dataclass, field

from app.models.enums import ActivityLevel, GoalPace, GoalType, Sex

DISCLAIMER = (
    "These numbers are estimates from the Mifflin-St Jeor equation and standard activity factors. "
    "Individual needs vary. This is not medical advice; talk to a doctor or registered dietitian "
    "before making significant changes, especially if you are pregnant, breastfeeding, or managing a health condition."
)

ACTIVITY_FACTORS: dict[ActivityLevel, float] = {
    ActivityLevel.sedentary: 1.2,
    ActivityLevel.lightly_active: 1.375,
    ActivityLevel.moderately_active: 1.55,
    ActivityLevel.very_active: 1.725,
    ActivityLevel.extra_active: 1.9,
}

# Goal adjustment = percentage of TDEE, capped at an absolute number of kcal.
# Chosen to stay conservative: at most a 500 kcal/day deficit or 350 kcal/day surplus.
GOAL_ADJUSTMENTS: dict[tuple[GoalType, GoalPace], tuple[float, int]] = {
    (GoalType.lose, GoalPace.gentle): (-0.10, 300),
    (GoalType.lose, GoalPace.moderate): (-0.20, 500),
    (GoalType.gain, GoalPace.gentle): (0.05, 200),
    (GoalType.gain, GoalPace.moderate): (0.10, 350),
}

# Commonly cited minimum intakes without medical supervision.
CALORIE_FLOOR = {Sex.female: 1200, Sex.male: 1500}

# Protein in grams per kg of body weight.
PROTEIN_G_PER_KG = {GoalType.maintain: 1.2, GoalType.lose: 1.6, GoalType.gain: 1.6}
PROTEIN_MAX_SHARE = 0.35   # never more than 35 % of calories from protein
FAT_SHARE = 0.27           # 27 % of calories from fat
FAT_MIN_G_PER_KG = 0.6
FIBER_G_PER_1000_KCAL = 14


@dataclass
class Targets:
    formula: str
    bmr: int
    activity_factor: float
    tdee: int
    goal_type: GoalType
    goal_pace: GoalPace
    goal_adjustment: int
    calorie_floor: int
    floor_applied: bool
    calorie_target: int
    protein_g: int
    carbs_g: int
    fat_g: int
    fiber_g: int
    explanation: list[str] = field(default_factory=list)
    disclaimer: str = DISCLAIMER


def calculate_bmr(weight_kg: float, height_cm: float, age: int, sex: Sex) -> float:
    """Mifflin-St Jeor (1990).
    male:   10 x kg + 6.25 x cm - 5 x age + 5
    female: 10 x kg + 6.25 x cm - 5 x age - 161
    """
    base = 10 * weight_kg + 6.25 * height_cm - 5 * age
    return base + 5 if sex == Sex.male else base - 161


def calculate_tdee(bmr: float, activity_level: ActivityLevel) -> float:
    return bmr * ACTIVITY_FACTORS[activity_level]


def goal_adjustment(tdee: float, goal: GoalType, pace: GoalPace) -> int:
    if goal == GoalType.maintain:
        return 0
    share, cap = GOAL_ADJUSTMENTS[(goal, pace)]
    raw = tdee * share
    return int(round(max(raw, -cap) if raw < 0 else min(raw, cap)))


def _round10(value: float) -> int:
    return int(round(value / 10.0)) * 10


def calculate_targets(*, weight_kg: float, height_cm: float, age: int, sex: Sex,
                      activity_level: ActivityLevel, goal_type: GoalType,
                      goal_pace: GoalPace = GoalPace.gentle) -> Targets:
    weight_kg, height_cm = float(weight_kg), float(height_cm)
    bmr = calculate_bmr(weight_kg, height_cm, age, sex)
    factor = ACTIVITY_FACTORS[activity_level]
    tdee = calculate_tdee(bmr, activity_level)
    adjustment = goal_adjustment(tdee, goal_type, goal_pace)

    target = tdee + adjustment
    floor = CALORIE_FLOOR[sex]
    if goal_type == GoalType.lose:
        floor = max(floor, int(round(bmr)))
    floor_applied = target < floor
    if floor_applied:
        target = floor
    target = _round10(target)

    protein = min(weight_kg * PROTEIN_G_PER_KG[goal_type], target * PROTEIN_MAX_SHARE / 4)
    fat = max(target * FAT_SHARE / 9, weight_kg * FAT_MIN_G_PER_KG)
    carbs = max((target - protein * 4 - fat * 9) / 4, 0)
    fiber = target / 1000 * FIBER_G_PER_1000_KCAL

    sex_term = "+ 5" if sex == Sex.male else "- 161"
    explanation = [
        f"BMR = 10 x {weight_kg:g} kg + 6.25 x {height_cm:g} cm - 5 x {age} {sex_term} = {bmr:.0f} kcal "
        f"(Mifflin-St Jeor, {sex.value} equation).",
        f"Maintenance (TDEE) = BMR x {factor} activity factor = {tdee:.0f} kcal.",
    ]
    if goal_type == GoalType.maintain:
        explanation.append("Goal is to maintain weight, so the target equals maintenance.")
    else:
        word = "deficit" if adjustment < 0 else "surplus"
        explanation.append(f"A {goal_pace.value} {word} of {abs(adjustment)} kcal is applied for your goal.")
    if floor_applied:
        explanation.append(f"The target was raised to a minimum of {floor} kcal to avoid an overly low intake.")
    explanation.append(
        f"Protein {protein:.0f} g ({PROTEIN_G_PER_KG[goal_type]} g/kg), fat about {int(FAT_SHARE * 100)} % of "
        f"calories, carbohydrates fill the rest."
    )

    return Targets(
        formula="Mifflin-St Jeor",
        bmr=int(round(bmr)),
        activity_factor=factor,
        tdee=int(round(tdee)),
        goal_type=goal_type,
        goal_pace=goal_pace,
        goal_adjustment=adjustment,
        calorie_floor=floor,
        floor_applied=floor_applied,
        calorie_target=target,
        protein_g=int(round(protein)),
        carbs_g=int(round(carbs)),
        fat_g=int(round(fat)),
        fiber_g=int(round(fiber)),
        explanation=explanation,
    )


def scale_nutrition(per_100g: dict[str, float], quantity_g: float) -> dict[str, float]:
    """Nutrition for an actual quantity: value_per_100g x grams / 100.
    e.g. 130 kcal/100 g x 150 g / 100 = 195 kcal."""
    factor = float(quantity_g) / 100.0
    return {
        "calories": round(float(per_100g["calories"]) * factor, 2),
        "protein_g": round(float(per_100g["protein"]) * factor, 2),
        "carbs_g": round(float(per_100g["carbs"]) * factor, 2),
        "fat_g": round(float(per_100g["fat"]) * factor, 2),
        "fiber_g": round(float(per_100g["fiber"]) * factor, 2),
    }


def food_per_100g(food) -> dict[str, float]:
    return {
        "calories": float(food.calories_per_100g),
        "protein": float(food.protein_per_100g),
        "carbs": float(food.carbs_per_100g),
        "fat": float(food.fat_per_100g),
        "fiber": float(food.fiber_per_100g),
    }
