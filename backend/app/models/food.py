import uuid
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Numeric, String, Text, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, JSONType, TimestampMixin
from app.models.enums import DietType, db_enum


class FoodItem(Base, TimestampMixin):
    """Nutrition values are per 100 g of the food *as described in its name*
    (e.g. "cooked" vs "raw/dry")."""
    __tablename__ = "food_items"
    __table_args__ = (
        CheckConstraint(
            "calories_per_100g >= 0 AND protein_per_100g >= 0 AND carbs_per_100g >= 0 "
            "AND fat_per_100g >= 0 AND fiber_per_100g >= 0",
            name="non_negative",
        ),
        CheckConstraint("protein_per_100g + carbs_per_100g + fat_per_100g <= 100.5", name="macros_le_100g"),
        # Global foods have unique names; each user's custom foods have unique names per user.
        Index("uq_food_items_global_name", func.lower(text("name")), unique=True,
              postgresql_where=text("created_by_user_id IS NULL")),
        Index("uq_food_items_user_name", "created_by_user_id", func.lower(text("name")), unique=True,
              postgresql_where=text("created_by_user_id IS NOT NULL")),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    calories_per_100g: Mapped[Decimal] = mapped_column(Numeric(7, 2), nullable=False)
    protein_per_100g: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    carbs_per_100g: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    fat_per_100g: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    fiber_per_100g: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=0, nullable=False)
    serving_unit: Mapped[str] = mapped_column(String(40), default="100 g", nullable=False)
    serving_size_g: Mapped[Decimal] = mapped_column(Numeric(6, 1), default=100, nullable=False)
    diet_type: Mapped[DietType] = mapped_column(db_enum(DietType, "diet_type"), nullable=False)
    allergens: Mapped[list] = mapped_column(JSONType, default=list, nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(500))
    source: Mapped[str] = mapped_column(Text, nullable=False)
    is_approximate: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # NULL = shared catalogue item; otherwise a private custom food.
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
