import uuid
from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationFailedError
from app.models.enums import EntrySource, MealType
from app.models.food import FoodItem
from app.models.meal import MealEntry
from app.models.user import User
from app.repositories import foods as food_repo
from app.schemas.meal import (DailyMealsOut, DayTotals, MealCreate, MealGroup, MealOut, MealUpdate, NutritionTotals,
                              WeeklyMealsOut)
from app.services.nutrition_calculator import food_per_100g, scale_nutrition

MEAL_ORDER = [MealType.breakfast, MealType.lunch, MealType.dinner, MealType.snacks]


def to_meal_out(entry: MealEntry) -> MealOut:
    return MealOut(
        id=entry.id, food_item_id=entry.food_item_id, food_name=entry.food.name, food_category=entry.food.category,
        meal_type=entry.meal_type, consumed_on=entry.consumed_on, quantity_g=float(entry.quantity_g),
        calories=float(entry.calories), protein_g=float(entry.protein_g), carbs_g=float(entry.carbs_g),
        fat_g=float(entry.fat_g), fiber_g=float(entry.fiber_g), source=entry.source,
        dispensing_command_id=entry.dispensing_command_id, created_at=entry.created_at,
    )


def _apply_nutrition(entry: MealEntry, food: FoodItem, quantity_g: float) -> None:
    values = scale_nutrition(food_per_100g(food), quantity_g)
    entry.quantity_g = quantity_g
    entry.calories = values["calories"]
    entry.protein_g = values["protein_g"]
    entry.carbs_g = values["carbs_g"]
    entry.fat_g = values["fat_g"]
    entry.fiber_g = values["fiber_g"]


def build_entry(*, user_id: uuid.UUID, food: FoodItem, meal_type: MealType, quantity_g: float, consumed_on: date,
                source: EntrySource = EntrySource.manual, dispensing_command_id: uuid.UUID | None = None) -> MealEntry:
    """Creates (but does not commit) a meal entry, so callers can include it in a larger transaction."""
    entry = MealEntry(user_id=user_id, food_item_id=food.id, meal_type=meal_type, consumed_on=consumed_on,
                      source=source, dispensing_command_id=dispensing_command_id)
    entry.food = food
    _apply_nutrition(entry, food, quantity_g)
    return entry


def create_meal(db: Session, user: User, data: MealCreate) -> MealOut:
    food = food_repo.get_visible(db, data.food_item_id, user.id)
    if food is None:
        raise ValidationFailedError("Choose a food from the list.", code="unknown_food")
    entry = build_entry(user_id=user.id, food=food, meal_type=data.meal_type, quantity_g=data.quantity_g,
                        consumed_on=data.consumed_on or date.today())
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return to_meal_out(entry)


def _owned_entry(db: Session, user: User, entry_id: uuid.UUID) -> MealEntry:
    entry = db.scalar(select(MealEntry).where(MealEntry.id == entry_id, MealEntry.user_id == user.id))
    if entry is None:
        raise NotFoundError("Meal entry not found.")
    return entry


def update_meal(db: Session, user: User, entry_id: uuid.UUID, data: MealUpdate) -> MealOut:
    entry = _owned_entry(db, user, entry_id)
    if data.meal_type is not None:
        entry.meal_type = data.meal_type
    if data.consumed_on is not None:
        entry.consumed_on = data.consumed_on
    if data.quantity_g is not None:
        if entry.source == EntrySource.dispenser:
            raise ValidationFailedError(
                "This amount was measured by the dispenser's scale. Delete the entry and log it manually if it "
                "needs to change.", code="measured_quantity_locked")
        _apply_nutrition(entry, entry.food, data.quantity_g)
    db.commit()
    db.refresh(entry)
    return to_meal_out(entry)


def delete_meal(db: Session, user: User, entry_id: uuid.UUID) -> None:
    entry = _owned_entry(db, user, entry_id)
    db.delete(entry)
    db.commit()


def _totals(entries) -> NutritionTotals:
    t = NutritionTotals()
    for e in entries:
        t.calories += e.calories
        t.protein_g += e.protein_g
        t.carbs_g += e.carbs_g
        t.fat_g += e.fat_g
        t.fiber_g += e.fiber_g
    return NutritionTotals(**{k: round(v, 1) for k, v in t.model_dump().items()})


def daily_meals(db: Session, user: User, day: date) -> DailyMealsOut:
    entries = db.scalars(
        select(MealEntry).where(MealEntry.user_id == user.id, MealEntry.consumed_on == day)
        .order_by(MealEntry.created_at)
    ).unique()
    grouped: dict[MealType, list[MealOut]] = defaultdict(list)
    all_out = []
    for e in entries:
        out = to_meal_out(e)
        grouped[e.meal_type].append(out)
        all_out.append(out)
    groups = [MealGroup(meal_type=m, entries=grouped[m], totals=_totals(grouped[m])) for m in MEAL_ORDER]
    return DailyMealsOut(date=day, meals=groups, totals=_totals(all_out))


def range_totals(db: Session, user: User, start: date, end: date) -> list[DayTotals]:
    rows = db.execute(
        select(MealEntry.consumed_on, func.sum(MealEntry.calories), func.sum(MealEntry.protein_g),
               func.sum(MealEntry.carbs_g), func.sum(MealEntry.fat_g), func.sum(MealEntry.fiber_g),
               func.count(MealEntry.id))
        .where(MealEntry.user_id == user.id, MealEntry.consumed_on.between(start, end))
        .group_by(MealEntry.consumed_on)
    ).all()
    by_day = {r[0]: r for r in rows}
    days = []
    current = start
    while current <= end:
        r = by_day.get(current)
        if r:
            days.append(DayTotals(date=current, calories=round(float(r[1]), 1), protein_g=round(float(r[2]), 1),
                                  carbs_g=round(float(r[3]), 1), fat_g=round(float(r[4]), 1),
                                  fiber_g=round(float(r[5]), 1), entries=r[6]))
        else:
            days.append(DayTotals(date=current))
        current += timedelta(days=1)
    return days


def weekly_meals(db: Session, user: User, end: date) -> WeeklyMealsOut:
    start = end - timedelta(days=6)
    return WeeklyMealsOut(start_date=start, end_date=end, days=range_totals(db, user, start, end))
