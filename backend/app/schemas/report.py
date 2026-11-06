from datetime import date

from pydantic import BaseModel


class ReportDay(BaseModel):
    date: date
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float
    entries: int


class TopFood(BaseModel):
    food_name: str
    times_logged: int
    total_quantity_g: float
    total_calories: float


class ReportOut(BaseModel):
    period: str
    start_date: date
    end_date: date
    calorie_target: int | None
    days: list[ReportDay]
    days_logged: int
    average_calories: float
    average_protein_g: float
    average_carbs_g: float
    average_fat_g: float
    days_on_target: int
    on_target_rule: str
    top_foods: list[TopFood]
    dispensed_count: int
    dispensed_total_g: float
