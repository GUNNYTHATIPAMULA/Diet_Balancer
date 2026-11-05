import uuid

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.food import FoodItem


def visible_to(user_id: uuid.UUID):
    """Shared catalogue foods plus the user's own custom foods."""
    return or_(FoodItem.created_by_user_id.is_(None), FoodItem.created_by_user_id == user_id)


def get_visible(db: Session, food_id: uuid.UUID, user_id: uuid.UUID) -> FoodItem | None:
    return db.scalar(select(FoodItem).where(FoodItem.id == food_id, visible_to(user_id)))


def list_visible(db: Session, user_id: uuid.UUID) -> list[FoodItem]:
    return list(db.scalars(select(FoodItem).where(visible_to(user_id)).order_by(FoodItem.name)))
