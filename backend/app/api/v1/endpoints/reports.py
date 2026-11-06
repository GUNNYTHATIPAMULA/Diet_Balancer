from datetime import date

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession
from app.schemas.report import ReportOut
from app.services import report_service

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/weekly", response_model=ReportOut)
def weekly(user: CurrentUser, db: DbSession, end: date | None = None):
    return report_service.weekly(db, user, end or date.today())


@router.get("/monthly", response_model=ReportOut)
def monthly(user: CurrentUser, db: DbSession, year: int | None = Query(None, ge=2000, le=2100),
            month: int | None = Query(None, ge=1, le=12)):
    today = date.today()
    return report_service.monthly(db, user, year or today.year, month or today.month)
