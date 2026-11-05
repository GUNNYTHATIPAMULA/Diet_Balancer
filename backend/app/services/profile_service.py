from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models.profile import FitnessGoal, UserProfile
from app.models.user import User
from app.repositories import users as user_repo
from app.schemas.profile import ProfileIn, ProfileOut, TargetsOut, WeightUpdate
from app.services.nutrition_calculator import Targets, calculate_targets


def targets_for(profile: UserProfile, goal: FitnessGoal) -> Targets:
    return calculate_targets(
        weight_kg=float(profile.weight_kg), height_cm=float(profile.height_cm), age=profile.age, sex=profile.sex,
        activity_level=profile.activity_level, goal_type=goal.goal_type, goal_pace=goal.pace,
    )


def _out(profile: UserProfile, goal: FitnessGoal) -> ProfileOut:
    return ProfileOut(
        age=profile.age, sex=profile.sex, height_cm=float(profile.height_cm), weight_kg=float(profile.weight_kg),
        activity_level=profile.activity_level, goal_type=goal.goal_type, goal_pace=goal.pace,
        target_weight_kg=float(goal.target_weight_kg) if goal.target_weight_kg is not None else None,
        dietary_preference=profile.dietary_preference, allergies=list(profile.allergies or []),
        restrictions=list(profile.restrictions or []), meals_per_day=profile.meals_per_day,
        updated_at=profile.updated_at, targets=TargetsOut(**targets_for(profile, goal).__dict__),
    )


def get_profile_and_goal(db: Session, user: User) -> tuple[UserProfile, FitnessGoal]:
    profile = user_repo.get_profile(db, user.id)
    goal = user_repo.get_active_goal(db, user.id)
    if profile is None or goal is None:
        raise NotFoundError("Complete your profile to see calorie targets.", code="profile_incomplete")
    return profile, goal


def get_targets_or_none(db: Session, user: User) -> Targets | None:
    profile = user_repo.get_profile(db, user.id)
    goal = user_repo.get_active_goal(db, user.id)
    if profile is None or goal is None:
        return None
    return targets_for(profile, goal)


def get_profile(db: Session, user: User) -> ProfileOut:
    return _out(*get_profile_and_goal(db, user))


def upsert_profile(db: Session, user: User, data: ProfileIn) -> ProfileOut:
    profile = user_repo.get_profile(db, user.id)
    fields = data.model_dump(exclude={"goal_type", "goal_pace", "target_weight_kg"})
    if profile is None:
        profile = UserProfile(user_id=user.id, **fields)
        db.add(profile)
    else:
        for key, value in fields.items():
            setattr(profile, key, value)

    goal = user_repo.get_active_goal(db, user.id)
    goal_changed = goal is None or (goal.goal_type, goal.pace) != (data.goal_type, data.goal_pace) or (
        (float(goal.target_weight_kg) if goal.target_weight_kg is not None else None) != data.target_weight_kg
    )
    if goal_changed:
        if goal is not None:
            goal.is_active = False
            db.flush()  # release the partial unique index before inserting the new active goal
        goal = FitnessGoal(user_id=user.id, goal_type=data.goal_type, pace=data.goal_pace,
                           target_weight_kg=data.target_weight_kg, is_active=True)
        db.add(goal)
    db.commit()
    db.refresh(profile)
    return _out(profile, goal)


def update_weight(db: Session, user: User, data: WeightUpdate) -> ProfileOut:
    profile, goal = get_profile_and_goal(db, user)
    profile.weight_kg = data.weight_kg
    db.commit()
    db.refresh(profile)
    return _out(profile, goal)


def get_calorie_target(db: Session, user: User) -> TargetsOut:
    profile, goal = get_profile_and_goal(db, user)
    return TargetsOut(**targets_for(profile, goal).__dict__)
