import calendar
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import EntrySource
from app.models.food import FoodItem
from app.models.meal import MealEntry
from app.models.user import User
from app.schemas.report import ReportDay, ReportOut, TopFood
from app.services import meal_service, profile_service

ON_TARGET_BAND = 0.10


def _report(db: Session, user: User, period: str, start: date, end: date) -> ReportOut:
    days = meal_service.range_totals(db, user, start, end)
    logged = [d for d in days if d.entries > 0]
    targets = profile_service.get_targets_or_none(db, user)
    target = targets.calorie_target if targets else None

    def avg(attr):
        return round(sum(getattr(d, attr) for d in logged) / len(logged), 1) if logged else 0.0

    on_target = 0
    if target:
        on_target = sum(1 for d in logged if abs(d.calories - target) <= target * ON_TARGET_BAND)

    top_rows = db.execute(
        select(FoodItem.name, func.count(MealEntry.id), func.sum(MealEntry.quantity_g), func.sum(MealEntry.calories))
        .join(FoodItem, FoodItem.id == MealEntry.food_item_id)
        .where(MealEntry.user_id == user.id, MealEntry.consumed_on.between(start, end))
        .group_by(FoodItem.name).order_by(func.count(MealEntry.id).desc(), FoodItem.name).limit(5)
    ).all()
    dispensed = db.execute(
        select(func.count(MealEntry.id), func.coalesce(func.sum(MealEntry.quantity_g), 0))
        .where(MealEntry.user_id == user.id, MealEntry.source == EntrySource.dispenser,
               MealEntry.consumed_on.between(start, end))
    ).one()

    return ReportOut(
        period=period, start_date=start, end_date=end, calorie_target=target,
        days=[ReportDay(**d.model_dump()) for d in days],
        days_logged=len(logged),
        average_calories=avg("calories"), average_protein_g=avg("protein_g"),
        average_carbs_g=avg("carbs_g"), average_fat_g=avg("fat_g"),
        days_on_target=on_target,
        on_target_rule=f"Logged days within ±{int(ON_TARGET_BAND * 100)}% of your current calorie target.",
        top_foods=[TopFood(food_name=r[0], times_logged=r[1], total_quantity_g=round(float(r[2]), 1),
                           total_calories=round(float(r[3]), 1)) for r in top_rows],
        dispensed_count=dispensed[0], dispensed_total_g=round(float(dispensed[1]), 1),
    )


def weekly(db: Session, user: User, end: date) -> ReportOut:
    return _report(db, user, "weekly", end - timedelta(days=6), end)


def monthly(db: Session, user: User, year: int, month: int) -> ReportOut:
    start = date(year, month, 1)
    end = date(year, month, calendar.monthrange(year, month)[1])
    return _report(db, user, "monthly", start, end)
