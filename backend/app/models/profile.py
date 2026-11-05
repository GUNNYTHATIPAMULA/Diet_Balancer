import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (Boolean, CheckConstraint, DateTime, ForeignKey, Index, Numeric, SmallInteger, Uuid,
                        func, text)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, JSONType, TimestampMixin
from app.models.enums import ActivityLevel, DietaryPreference, GoalPace, GoalType, Sex, db_enum


class UserProfile(Base, TimestampMixin):
    __tablename__ = "user_profiles"
    __table_args__ = (
        CheckConstraint("age BETWEEN 18 AND 100", name="age_range"),
        CheckConstraint("height_cm BETWEEN 120 AND 230", name="height_range"),
        CheckConstraint("weight_kg BETWEEN 30 AND 300", name="weight_range"),
        CheckConstraint("meals_per_day BETWEEN 1 AND 8", name="meals_range"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    age: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    sex: Mapped[Sex] = mapped_column(db_enum(Sex, "sex"), nullable=False)
    height_cm: Mapped[Decimal] = mapped_column(Numeric(5, 1), nullable=False)
    weight_kg: Mapped[Decimal] = mapped_column(Numeric(5, 1), nullable=False)
    activity_level: Mapped[ActivityLevel] = mapped_column(db_enum(ActivityLevel, "activity_level"), nullable=False)
    dietary_preference: Mapped[DietaryPreference] = mapped_column(
        db_enum(DietaryPreference, "dietary_preference"), default=DietaryPreference.none, nullable=False
    )
    allergies: Mapped[list] = mapped_column(JSONType, default=list, nullable=False)
    restrictions: Mapped[list] = mapped_column(JSONType, default=list, nullable=False)
    meals_per_day: Mapped[int] = mapped_column(SmallInteger, default=3, nullable=False)

    user: Mapped["User"] = relationship(back_populates="profile")  # noqa: F821


class FitnessGoal(Base):
    """Goal history. Exactly one active goal per user (enforced by a partial unique index)."""
    __tablename__ = "fitness_goals"
    __table_args__ = (
        Index("uq_fitness_goals_active_user", "user_id", unique=True, postgresql_where=text("is_active")),
        CheckConstraint("target_weight_kg IS NULL OR target_weight_kg BETWEEN 30 AND 300", name="target_range"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    goal_type: Mapped[GoalType] = mapped_column(db_enum(GoalType, "goal_type"), nullable=False)
    pace: Mapped[GoalPace] = mapped_column(db_enum(GoalPace, "goal_pace"), default=GoalPace.gentle, nullable=False)
    target_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(5, 1))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
