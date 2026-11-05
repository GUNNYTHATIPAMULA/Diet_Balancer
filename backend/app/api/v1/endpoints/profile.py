from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.profile import ProfileIn, ProfileOut, TargetsOut, WeightUpdate
from app.services import profile_service

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("", response_model=ProfileOut)
def get_profile(user: CurrentUser, db: DbSession):
    return profile_service.get_profile(db, user)


@router.put("", response_model=ProfileOut)
def save_profile(data: ProfileIn, user: CurrentUser, db: DbSession):
    return profile_service.upsert_profile(db, user, data)


@router.patch("/weight", response_model=ProfileOut)
def update_weight(data: WeightUpdate, user: CurrentUser, db: DbSession):
    return profile_service.update_weight(db, user, data)


@router.get("/calorie-target", response_model=TargetsOut)
def calorie_target(user: CurrentUser, db: DbSession):
    return profile_service.get_calorie_target(db, user)
