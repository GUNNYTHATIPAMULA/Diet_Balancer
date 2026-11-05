from datetime import date

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession
from app.schemas.nutrition import RecommendationsOut, SummaryOut
from app.services import nutrition_service

router = APIRouter(prefix="/nutrition", tags=["nutrition"])


@router.get("/summary", response_model=SummaryOut)
def summary(user: CurrentUser, db: DbSession, day: date | None = None):
    return nutrition_service.summary(db, user, day or date.today())


@router.get("/recommendations", response_model=RecommendationsOut)
def recommendations(user: CurrentUser, db: DbSession, day: date | None = None,
                    limit: int = Query(8, ge=1, le=20)):
    return nutrition_service.recommendations(db, user, day or date.today(), limit)
