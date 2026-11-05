import uuid
from datetime import date

from pydantic import BaseModel

from app.schemas.meal import MealGroup, NutritionTotals
from app.schemas.profile import TargetsOut


class SummaryOut(BaseModel):
    date: date
    has_profile: bool
    targets: TargetsOut | None
    consumed: NutritionTotals
    remaining: NutritionTotals | None
    meals: list[MealGroup]
    macro_split_percent: dict[str, float]


class RecommendationOut(BaseModel):
    food_id: uuid.UUID
    food_name: str
    category: str
    suggested_quantity_g: float
    serving_hint: str
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    score: float
    reasons: list[str]
    is_approximate: bool


class RecommendationsOut(BaseModel):
    date: date
    engine: str
    focus: str
    message: str
    remaining: NutritionTotals | None
    items: list[RecommendationOut]
    excluded_count: int
