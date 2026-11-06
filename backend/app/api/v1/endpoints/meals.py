import uuid
from datetime import date

from fastapi import APIRouter, Response, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.meal import DailyMealsOut, MealCreate, MealOut, MealUpdate, WeeklyMealsOut
from app.services import meal_service

router = APIRouter(prefix="/meals", tags=["meals"])


@router.post("", response_model=MealOut, status_code=status.HTTP_201_CREATED)
def create_meal(data: MealCreate, user: CurrentUser, db: DbSession):
    return meal_service.create_meal(db, user, data)


@router.get("/daily", response_model=DailyMealsOut)
def daily(user: CurrentUser, db: DbSession, day: date | None = None):
    return meal_service.daily_meals(db, user, day or date.today())


@router.get("/weekly", response_model=WeeklyMealsOut)
def weekly(user: CurrentUser, db: DbSession, end: date | None = None):
    return meal_service.weekly_meals(db, user, end or date.today())


@router.patch("/{entry_id}", response_model=MealOut)
def update_meal(entry_id: uuid.UUID, data: MealUpdate, user: CurrentUser, db: DbSession):
    return meal_service.update_meal(db, user, entry_id, data)


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_meal(entry_id: uuid.UUID, user: CurrentUser, db: DbSession):
    meal_service.delete_meal(db, user, entry_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
