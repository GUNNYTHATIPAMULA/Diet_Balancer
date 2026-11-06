import uuid

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.meal_plan import MealPlanCreate, MealPlanOut, ServeMealIn
from app.services import meal_plan_service

router = APIRouter(prefix="/dispenser/meal-plans", tags=["meal plans"])


@router.post("", response_model=MealPlanOut, status_code=status.HTTP_201_CREATED)
def generate(data: MealPlanCreate, user: CurrentUser, db: DbSession):
    """Generate My Meal: portions from the containers' foods for this user's remaining targets."""
    return meal_plan_service.generate(db, user, data)


@router.get("", response_model=list[MealPlanOut])
def list_plans(user: CurrentUser, db: DbSession, device_id: uuid.UUID | None = None,
               limit: int = Query(5, ge=1, le=50)):
    return meal_plan_service.list_recent(db, user, device_id, limit)


@router.get("/{plan_id}", response_model=MealPlanOut)
def get_plan(plan_id: uuid.UUID, user: CurrentUser, db: DbSession):
    return meal_plan_service.get(db, user, plan_id)


@router.post("/{plan_id}/serve", response_model=MealPlanOut)
def serve(plan_id: uuid.UUID, data: ServeMealIn, user: CurrentUser, db: DbSession):
    """Serve Meal: queues one measured dispense per food. Safe to retry (a served plan is returned as is)."""
    return meal_plan_service.serve(db, user, plan_id, data)


@router.post("/{plan_id}/stop", response_model=MealPlanOut)
def stop(plan_id: uuid.UUID, user: CurrentUser, db: DbSession):
    return meal_plan_service.stop(db, user, plan_id)
