import uuid

from fastapi import APIRouter, Query, Response, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.food import FoodCreate, FoodListOut, FoodOut
from app.services import food_service

router = APIRouter(prefix="/foods", tags=["foods"])


@router.get("", response_model=FoodListOut)
def list_foods(user: CurrentUser, db: DbSession, category: str | None = None,
               limit: int = Query(100, ge=1, le=200), offset: int = Query(0, ge=0)):
    return food_service.list_foods(db, user, category=category, limit=limit, offset=offset)


@router.get("/search", response_model=FoodListOut)
def search(user: CurrentUser, db: DbSession, q: str = Query(min_length=1, max_length=80),
           limit: int = Query(20, ge=1, le=50)):
    return food_service.search_foods(db, user, q, limit)


@router.get("/categories", response_model=list[str])
def categories(user: CurrentUser, db: DbSession):
    return food_service.categories(db, user)


@router.post("", response_model=FoodOut, status_code=status.HTTP_201_CREATED)
def create_food(data: FoodCreate, user: CurrentUser, db: DbSession):
    return food_service.create_custom_food(db, user, data)


@router.get("/{food_id}", response_model=FoodOut)
def get_food(food_id: uuid.UUID, user: CurrentUser, db: DbSession):
    return food_service.get_food(db, user, food_id)


@router.delete("/{food_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_food(food_id: uuid.UUID, user: CurrentUser, db: DbSession):
    food_service.delete_custom_food(db, user, food_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
