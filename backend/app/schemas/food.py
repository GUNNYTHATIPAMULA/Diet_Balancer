import uuid

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.enums import ALLERGENS, DietType
from app.schemas.common import ORMModel
from app.schemas.profile import Allergen


class FoodOut(ORMModel):
    id: uuid.UUID
    name: str
    category: str
    calories_per_100g: float
    protein_per_100g: float
    carbs_per_100g: float
    fat_per_100g: float
    fiber_per_100g: float
    serving_unit: str
    serving_size_g: float
    diet_type: DietType
    allergens: list[str]
    image_url: str | None
    source: str
    is_approximate: bool
    is_custom: bool = False

    @model_validator(mode="before")
    @classmethod
    def mark_custom(cls, data):
        if hasattr(data, "created_by_user_id"):
            return {**{c: getattr(data, c) for c in cls.model_fields if c != "is_custom"},
                    "is_custom": data.created_by_user_id is not None}
        return data


class FoodListOut(BaseModel):
    items: list[FoodOut]
    total: int


class FoodCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    category: str = Field(min_length=2, max_length=60)
    calories_per_100g: float = Field(ge=0, le=950)
    protein_per_100g: float = Field(ge=0, le=100)
    carbs_per_100g: float = Field(ge=0, le=100)
    fat_per_100g: float = Field(ge=0, le=100)
    fiber_per_100g: float = Field(default=0, ge=0, le=100)
    serving_unit: str = Field(default="100 g", max_length=40)
    serving_size_g: float = Field(default=100, gt=0, le=2000)
    diet_type: DietType
    allergens: list[Allergen] = Field(default_factory=list, max_length=len(ALLERGENS))
    source: str = Field(default="Entered by user (from package label or own measurement)", max_length=255)

    @field_validator("name", "category")
    @classmethod
    def tidy(cls, value: str) -> str:
        return " ".join(value.split())

    @model_validator(mode="after")
    def macros_fit(self):
        if self.protein_per_100g + self.carbs_per_100g + self.fat_per_100g > 100.5:
            raise ValueError("Protein, carbohydrates and fat cannot add up to more than 100 g per 100 g.")
        return self
