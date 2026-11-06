import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.profile import FitnessGoal, UserProfile
from app.models.user import User


def get_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.lower()))


def get_by_id(db: Session, user_id: uuid.UUID) -> User | None:
    return db.get(User, user_id)


def get_profile(db: Session, user_id: uuid.UUID) -> UserProfile | None:
    return db.scalar(select(UserProfile).where(UserProfile.user_id == user_id))


def get_active_goal(db: Session, user_id: uuid.UUID) -> FitnessGoal | None:
    return db.scalar(select(FitnessGoal).where(FitnessGoal.user_id == user_id, FitnessGoal.is_active.is_(True)))
