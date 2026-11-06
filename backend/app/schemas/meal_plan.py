import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.enums import MealPlanStatus, MealType
from app.schemas.device import CommandOut


class MealPlanCreate(BaseModel):
    device_id: uuid.UUID
    meal_type: MealType
    consumed_on: date | None = None
    container_ids: list[uuid.UUID] | None = Field(default=None, description="Limit the plan to these containers.")


class MealPlanItem(BaseModel):
    container_id: uuid.UUID
    container_label: str
    slot_number: int
    food_id: uuid.UUID
    food_name: str
    categories: list[str]
    grams: float
    nutrition: dict
    reasons: list[str]
    command: CommandOut | None = None


class MealPlanOut(BaseModel):
    id: uuid.UUID
    device_id: uuid.UUID
    status: MealPlanStatus
    meal_type: MealType
    consumed_on: date
    engine: str
    remaining_today: dict
    meal_target: dict
    items: list[MealPlanItem]
    estimated_totals: dict
    measured_totals: dict | None
    explanation: list[str]
    skipped: list[str]
    created_at: datetime
    served_at: datetime | None


class ServeItem(BaseModel):
    container_id: uuid.UUID
    grams: float = Field(ge=0, le=500)


class ServeMealIn(BaseModel):
    items: list[ServeItem] | None = Field(default=None, description="Adjusted grams; omit to serve as planned.")
