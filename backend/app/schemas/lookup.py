import uuid
from typing import Literal

from pydantic import BaseModel, Field

from app.models.enums import DietType
from app.schemas.profile import Allergen


class FoodCandidate(BaseModel):
    source: Literal["catalogue", "usda_fdc"]
    food_id: uuid.UUID | None
    external_id: str | None
    name: str
    category: str
    calories_per_100g: float
    protein_per_100g: float
    carbs_per_100g: float
    fat_per_100g: float
    fiber_per_100g: float
    categories: list[str]
    primary_category: str | None
    classification_reasons: list[str]
    diet_type: str
    allergens: list[str]
    data_source: str
    is_approximate: bool
    dispenser_friendly: bool
    match: str
    is_custom: bool


class IdentifyOut(BaseModel):
    query: str
    candidates: list[FoodCandidate]
    external_provider: str | None
    external_error: str | None


class ImportFoodIn(BaseModel):
    source: Literal["usda_fdc"] = "usda_fdc"
    external_id: str = Field(pattern=r"^\d{1,12}$")
    diet_type: DietType = DietType.unknown
    allergens: list[Allergen] = Field(default_factory=list)
