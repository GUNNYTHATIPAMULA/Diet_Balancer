import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.enums import EntrySource, MealType


class MealCreate(BaseModel):
    food_item_id: uuid.UUID
    meal_type: MealType
    quantity_g: float = Field(gt=0, le=5000)
    consumed_on: date | None = None


class MealUpdate(BaseModel):
    meal_type: MealType | None = None
    quantity_g: float | None = Field(default=None, gt=0, le=5000)
    consumed_on: date | None = None


class NutritionTotals(BaseModel):
    calories: float = 0
    protein_g: float = 0
    carbs_g: float = 0
    fat_g: float = 0
    fiber_g: float = 0


class MealOut(BaseModel):
    id: uuid.UUID
    food_item_id: uuid.UUID
    food_name: str
    food_category: str
    meal_type: MealType
    consumed_on: date
    quantity_g: float
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float
    source: EntrySource
    dispensing_command_id: uuid.UUID | None
    created_at: datetime


class MealGroup(BaseModel):
    meal_type: MealType
    entries: list[MealOut]
    totals: NutritionTotals


class DailyMealsOut(BaseModel):
    date: date
    meals: list[MealGroup]
    totals: NutritionTotals


class DayTotals(NutritionTotals):
    date: date
    entries: int = 0


class WeeklyMealsOut(BaseModel):
    start_date: date
    end_date: date
    days: list[DayTotals]
