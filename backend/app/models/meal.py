import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Numeric, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import EntrySource, MealType, db_enum


class MealEntry(Base, TimestampMixin):
    """A logged portion of food.

    The nutrition columns are a snapshot calculated at logging time. This is
    deliberate, not accidental duplication: if a food's reference values are
    corrected later, past days keep the numbers the user actually saw."""
    __tablename__ = "meal_entries"
    __table_args__ = (
        CheckConstraint("quantity_g > 0 AND quantity_g <= 5000", name="quantity_range"),
        Index("ix_meal_entries_user_day", "user_id", "consumed_on"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    food_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("food_items.id"), nullable=False)
    meal_type: Mapped[MealType] = mapped_column(db_enum(MealType, "meal_type"), nullable=False)
    consumed_on: Mapped[date] = mapped_column(Date, nullable=False)
    quantity_g: Mapped[Decimal] = mapped_column(Numeric(7, 1), nullable=False)
    calories: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    protein_g: Mapped[Decimal] = mapped_column(Numeric(7, 2), nullable=False)
    carbs_g: Mapped[Decimal] = mapped_column(Numeric(7, 2), nullable=False)
    fat_g: Mapped[Decimal] = mapped_column(Numeric(7, 2), nullable=False)
    fiber_g: Mapped[Decimal] = mapped_column(Numeric(7, 2), nullable=False)
    source: Mapped[EntrySource] = mapped_column(db_enum(EntrySource, "entry_source"), default=EntrySource.manual,
                                                nullable=False)
    # Set when the entry came from a confirmed dispenser operation. Unique, so a
    # retried result can never create a second entry for the same command.
    dispensing_command_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("dispensing_commands.id", ondelete="SET NULL"), unique=True
    )

    food: Mapped["FoodItem"] = relationship(lazy="joined")  # noqa: F821
