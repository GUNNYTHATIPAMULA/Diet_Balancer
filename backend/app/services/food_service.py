import uuid

from sqlalchemy import String, case, cast, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.models.food import FoodItem
from app.models.user import User
from app.repositories import foods as food_repo
from app.schemas.food import FoodCreate, FoodListOut, FoodOut


def list_foods(db: Session, user: User, *, category: str | None, limit: int, offset: int) -> FoodListOut:
    stmt = select(FoodItem).where(food_repo.visible_to(user.id))
    if category:
        stmt = stmt.where(FoodItem.category == category)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    items = db.scalars(stmt.order_by(FoodItem.category, FoodItem.name).limit(limit).offset(offset))
    return FoodListOut(items=[FoodOut.model_validate(i) for i in items], total=total or 0)


def search_foods(db: Session, user: User, query: str, limit: int) -> FoodListOut:
    term = " ".join(query.split()).lower()
    if not term:
        return FoodListOut(items=[], total=0)
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    name = func.lower(FoodItem.name)
    rank = case((name == term, 0), (name.like(f"{escaped}%", escape="\\"), 1), else_=2)
    stmt = (
        select(FoodItem)
        .where(food_repo.visible_to(user.id),
               (name.like(f"%{escaped}%", escape="\\"))
               | (func.lower(FoodItem.category).like(f"%{escaped}%", escape="\\"))
               | (func.lower(cast(FoodItem.aliases, String)).like(f"%\"{escaped}%", escape="\\")))
        .order_by(rank, FoodItem.name)
        .limit(limit)
    )
    items = [FoodOut.model_validate(i) for i in db.scalars(stmt)]
    return FoodListOut(items=items, total=len(items))


def categories(db: Session, user: User) -> list[str]:
    return list(db.scalars(select(FoodItem.category).where(food_repo.visible_to(user.id))
                           .distinct().order_by(FoodItem.category)))


def get_food(db: Session, user: User, food_id: uuid.UUID) -> FoodOut:
    food = food_repo.get_visible(db, food_id, user.id)
    if food is None:
        raise NotFoundError("Food not found.")
    return FoodOut.model_validate(food)


def create_custom_food(db: Session, user: User, data: FoodCreate) -> FoodOut:
    from app.services.nutrition_classifier import classify
    food = FoodItem(**data.model_dump(), created_by_user_id=user.id, is_approximate=True,
                    categories=classify(protein=data.protein_per_100g, carbs=data.carbs_per_100g,
                                        fat=data.fat_per_100g, fiber=data.fiber_per_100g).categories)
    db.add(food)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError("You already have a custom food with this name.", code="duplicate_food")
    db.refresh(food)
    return FoodOut.model_validate(food)


def delete_custom_food(db: Session, user: User, food_id: uuid.UUID) -> None:
    food = db.scalar(select(FoodItem).where(FoodItem.id == food_id, FoodItem.created_by_user_id == user.id))
    if food is None:
        raise NotFoundError("Custom food not found.")
    db.delete(food)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError("This food is used in your meal log, so it can't be deleted.", code="food_in_use")
