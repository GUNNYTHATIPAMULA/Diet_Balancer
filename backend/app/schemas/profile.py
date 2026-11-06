from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.enums import ALLERGENS, ActivityLevel, DietaryPreference, GoalPace, GoalType, Sex

Allergen = Literal[ALLERGENS]  # type: ignore[valid-type]


class ProfileIn(BaseModel):
    age: int = Field(ge=18, le=100, description="Estimates are designed for adults (18+).")
    sex: Sex = Field(description="Selects the male or female Mifflin-St Jeor equation.")
    height_cm: float = Field(ge=120, le=230)
    weight_kg: float = Field(ge=30, le=300)
    activity_level: ActivityLevel
    goal_type: GoalType = GoalType.maintain
    goal_pace: GoalPace = GoalPace.gentle
    target_weight_kg: float | None = Field(default=None, ge=30, le=300)
    dietary_preference: DietaryPreference = DietaryPreference.none
    allergies: list[Allergen] = Field(default_factory=list, max_length=len(ALLERGENS))
    restrictions: list[str] = Field(default_factory=list, max_length=20)
    meals_per_day: int = Field(default=3, ge=1, le=8)

    @field_validator("restrictions")
    @classmethod
    def clean_restrictions(cls, values: list[str]) -> list[str]:
        cleaned = []
        for value in values:
            value = " ".join(value.lower().split())
            if not value:
                continue
            if len(value) > 40:
                raise ValueError("Each restriction must be 40 characters or fewer.")
            if value not in cleaned:
                cleaned.append(value)
        return cleaned

    @field_validator("allergies")
    @classmethod
    def unique_allergies(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(values))

    @model_validator(mode="after")
    def target_matches_goal(self):
        target = self.target_weight_kg
        if target is None:
            return self
        if self.goal_type == GoalType.lose and target >= self.weight_kg:
            raise ValueError("For a weight-loss goal, the target weight must be below your current weight.")
        if self.goal_type == GoalType.gain and target <= self.weight_kg:
            raise ValueError("For a weight-gain goal, the target weight must be above your current weight.")
        return self


class WeightUpdate(BaseModel):
    weight_kg: float = Field(ge=30, le=300)


class TargetsOut(BaseModel):
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
    explanation: list[str]
    disclaimer: str


class ProfileOut(BaseModel):
    age: int
    sex: Sex
    height_cm: float
    weight_kg: float
    activity_level: ActivityLevel
    goal_type: GoalType
    goal_pace: GoalPace
    target_weight_kg: float | None
    dietary_preference: DietaryPreference
    allergies: list[str]
    restrictions: list[str]
    meals_per_day: int
    updated_at: datetime
    targets: TargetsOut
