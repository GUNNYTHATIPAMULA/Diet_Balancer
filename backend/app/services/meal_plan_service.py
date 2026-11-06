"""Generate My Meal / Serve Meal: plans from the containers' foods and serves them in sequence."""
import uuid
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ConflictError, NotFoundError, ValidationFailedError
from app.models.device import DeviceContainer, DispensingCommand, MealPlan
from app.models.enums import (ACTIVE_COMMAND_STATUSES, CommandStatus, CommandType, DietaryPreference, MealPlanStatus)
from app.models.user import User
from app.repositories import devices as device_repo
from app.repositories import users as user_repo
from app.schemas.meal_plan import MealPlanCreate, MealPlanItem, MealPlanOut, ServeMealIn
from app.services import dispenser_service, meal_service, profile_service
from app.services.meal_planner import PlanFood, nutrition_for, plan_meal
from app.services.recommendation_service import ALLOWED_DIET_TYPES
from app.utils.time import utcnow

ENGINE = "macro_balance_v1"


def _per100(food) -> dict:
    return {"kcal": float(food.calories_per_100g), "protein": float(food.protein_per_100g),
            "carbs": float(food.carbs_per_100g), "fat": float(food.fat_per_100g), "fiber": float(food.fiber_per_100g)}


def _max_portion(food) -> float:
    return float(min(max(3 * float(food.serving_size_g), 30.0), get_settings().DISPENSE_MAX_G))


def _remaining(db: Session, user: User, day: date) -> tuple[dict, int]:
    targets = profile_service.get_targets_or_none(db, user)
    if targets is None:
        raise ConflictError("Complete your profile first so your daily targets are known.", code="profile_incomplete")
    daily = meal_service.daily_meals(db, user, day)
    c = daily.totals
    remaining = {"kcal": round(targets.calorie_target - c.calories, 1), "protein": round(targets.protein_g - c.protein_g, 1),
                 "carbs": round(targets.carbs_g - c.carbs_g, 1), "fat": round(targets.fat_g - c.fat_g, 1)}
    profile = user_repo.get_profile(db, user.id)
    meals_logged = sum(1 for g in daily.meals if g.entries)
    meals_left = max((profile.meals_per_day if profile else 3) - meals_logged, 1)
    return remaining, meals_left


def _skip_reason(food, profile) -> str | None:
    if profile is None:
        return None
    pref = profile.dietary_preference
    if food.diet_type not in ALLOWED_DIET_TYPES[pref]:
        if food.diet_type.value == "unknown":
            return f"its diet type isn't confirmed, and your preference is {pref.value.replace('_', '-')}"
        return f"it doesn't fit your {pref.value.replace('_', '-')} preference"
    hit = set(food.allergens or []) & set(profile.allergies or [])
    if hit:
        return f"it contains {', '.join(sorted(hit))}, which you're allergic to"
    term = next((t for t in (profile.restrictions or []) if t and t in f"{food.name} {food.category}".lower()), None)
    if term:
        return f"you asked to avoid '{term}'"
    return None


def _owned_plan(db: Session, user: User, plan_id: uuid.UUID, lock: bool = False) -> MealPlan:
    stmt = select(MealPlan).where(MealPlan.id == plan_id, MealPlan.user_id == user.id)
    if lock:
        stmt = stmt.with_for_update()
    plan = db.scalar(stmt)
    if plan is None:
        raise NotFoundError("Meal plan not found.")
    return plan


def plan_out(db: Session, plan: MealPlan) -> MealPlanOut:
    cmds = {c.container_id: c for c in db.scalars(select(DispensingCommand)
                                                  .where(DispensingCommand.meal_plan_id == plan.id))}
    items = []
    measured = None
    for it in plan.items:
        cmd = cmds.get(uuid.UUID(it["container_id"]))
        out = dispenser_service.command_out(db, cmd, with_logs=False) if cmd else None
        if out and out.status == CommandStatus.completed and out.nutrition:
            measured = measured or {"calories": 0.0, "protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0, "grams": 0.0}
            for k in ("calories", "protein_g", "carbs_g", "fat_g"):
                measured[k] = round(measured[k] + out.nutrition[k], 1)
            measured["grams"] = round(measured["grams"] + (out.dispensed_weight_g or 0), 1)
        items.append(MealPlanItem(**{**it, "container_id": uuid.UUID(it["container_id"]),
                                     "food_id": uuid.UUID(it["food_id"])}, command=out))
    t = plan.targets or {}
    return MealPlanOut(
        id=plan.id, device_id=plan.device_id, status=plan.status, meal_type=plan.meal_type,
        consumed_on=plan.consumed_on, engine=plan.engine, remaining_today=t.get("remaining_today", {}),
        meal_target=t.get("meal_target", {}), items=items, estimated_totals=plan.totals or {},
        measured_totals=measured, explanation=list(plan.explanation or []), skipped=t.get("skipped", []),
        created_at=plan.created_at, served_at=plan.served_at)


def generate(db: Session, user: User, data: MealPlanCreate) -> MealPlanOut:
    device = device_repo.get_owned(db, data.device_id, user.id)
    if device is None:
        raise NotFoundError("Device not found.")
    day = data.consumed_on or date.today()
    remaining, meals_left = _remaining(db, user, day)
    profile = user_repo.get_profile(db, user.id)

    foods, skipped, by_key = [], [], {}
    for c in device.containers:
        if data.container_ids is not None and c.id not in data.container_ids:
            continue
        if not c.is_enabled:
            skipped.append(f"{c.label} is disabled.")
            continue
        if c.food is None:
            skipped.append(f"{c.label} has no food assigned.")
            continue
        reason = _skip_reason(c.food, profile)
        if reason:
            skipped.append(f"{c.label} ({c.food.name}) skipped: {reason}.")
            continue
        foods.append(PlanFood(key=str(c.id), name=c.food.name, per100=_per100(c.food), max_g=_max_portion(c.food)))
        by_key[str(c.id)] = c
    if not by_key:
        raise ValidationFailedError("No container has a usable food. Configure a container first.",
                                    code="no_usable_containers", details={"skipped": skipped})

    clipped = {k: max(v, 0.0) for k, v in remaining.items()}
    meal_target = {k: round(v / meals_left, 1) for k, v in clipped.items()}
    result = plan_meal(foods, meal_target, clipped)
    items = []
    for it in result.items:
        c = by_key[it.key]
        items.append({"container_id": str(c.id), "container_label": c.label, "slot_number": c.slot_number,
                      "food_id": str(c.food.id), "food_name": c.food.name, "categories": list(c.food.categories or []),
                      "grams": it.grams, "nutrition": it.nutrition, "reasons": it.reasons})
    explanation = [
        f"Aimed at {'all' if meals_left == 1 else f'1/{meals_left}'} of what's left today "
        f"({meals_left} meal{'s' if meals_left > 1 else ''} left): about {meal_target['kcal']:.0f} kcal, "
        f"{meal_target['protein']:.0f} g protein, {meal_target['carbs']:.0f} g carbs, {meal_target['fat']:.0f} g fat.",
        "Each food counts with all of its macronutrients, using its verified values per 100 g.",
        f"Estimated portions are approximate: the dispenser measures what is actually served "
        f"(±{get_settings().DISPENSE_TOLERANCE_PERCENT:g} % by default) and only that is logged.",
        *result.notes,
    ]
    plan = MealPlan(user_id=user.id, device_id=device.id, status=MealPlanStatus.proposed, meal_type=data.meal_type,
                    consumed_on=day, engine=ENGINE, items=items, totals=result.totals, explanation=explanation,
                    targets={"remaining_today": remaining, "meal_target": meal_target, "meals_left": meals_left,
                             "skipped": skipped})
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan_out(db, plan)


def get(db: Session, user: User, plan_id: uuid.UUID) -> MealPlanOut:
    plan = _owned_plan(db, user, plan_id)
    dispenser_service.expire_stale(db, plan.device_id)
    db.commit()
    db.refresh(plan)
    return plan_out(db, plan)


def list_recent(db: Session, user: User, device_id: uuid.UUID | None, limit: int) -> list[MealPlanOut]:
    stmt = select(MealPlan).where(MealPlan.user_id == user.id)
    if device_id:
        stmt = stmt.where(MealPlan.device_id == device_id)
    return [plan_out(db, p) for p in db.scalars(stmt.order_by(MealPlan.created_at.desc()).limit(limit))]


def serve(db: Session, user: User, plan_id: uuid.UUID, data: ServeMealIn) -> MealPlanOut:
    plan = _owned_plan(db, user, plan_id, lock=True)
    if plan.status != MealPlanStatus.proposed:
        return plan_out(db, plan)  # already served: repeat clicks/retries change nothing
    device = device_repo.get_owned(db, plan.device_id, user.id)
    dispenser_service.expire_stale(db, device.id)
    db.flush()
    dispenser_service.check_device_ready(db, device)

    grams = {it["container_id"]: it["grams"] for it in plan.items}
    if data.items is not None:
        grams = {str(i.container_id): i.grams for i in data.items}
    unknown = set(grams) - {it["container_id"] for it in plan.items}
    if unknown:
        raise ValidationFailedError("Only foods from this meal plan can be served.", code="not_in_plan")
    settings = get_settings()
    chosen = []
    for it in plan.items:
        g = float(grams.get(it["container_id"], 0))
        if g <= 0:
            continue
        if not settings.DISPENSE_MIN_G <= g <= settings.DISPENSE_MAX_G:
            raise ValidationFailedError(f"{it['food_name']}: choose between {settings.DISPENSE_MIN_G:g} and "
                                        f"{settings.DISPENSE_MAX_G:g} g.", code="target_out_of_range")
        container = device_repo.get_container(db, device.id, uuid.UUID(it["container_id"]))
        if container is None or not container.is_enabled or str(container.food_item_id) != it["food_id"]:
            raise ConflictError(f"{it['container_label']} changed since this meal was generated. Generate it again.",
                                code="plan_outdated")
        chosen.append((it, container, g))
    if not chosen:
        raise ValidationFailedError("Choose at least one food to serve.", code="empty_meal")

    from app.services.device_service import settings_of
    dispense_settings = settings_of(device)
    now = utcnow()
    ttl = timedelta(seconds=settings.COMMAND_PENDING_TTL_SECONDS)
    for seq, (it, container, g) in enumerate(chosen, start=1):
        cmd = DispensingCommand(
            device_id=device.id, user_id=user.id, container_id=container.id, food_item_id=container.food_item_id,
            command_type=CommandType.dispense, status=CommandStatus.pending if seq == 1 else CommandStatus.queued,
            idempotency_key=f"{plan.id}:{seq}", meal_plan_id=plan.id, sequence=seq, target_weight_g=g,
            meal_type=plan.meal_type, consumed_on=plan.consumed_on, log_to_meals=True,
            parameters=dispenser_service.build_params(container, dispense_settings), created_at=now,
            expires_at=now + ttl if seq == 1 else now + timedelta(days=1))
        db.add(cmd)
        db.flush()
        dispenser_service._log(db, cmd, "created" if seq == 1 else "queued",
                               f"Meal step {seq} of {len(chosen)}: {g:g} g of {it['food_name']}.", g)
    new_items = []
    for it in plan.items:
        g = float(grams.get(it["container_id"], 0))
        if g > 0:
            per100 = {k: (it["nutrition"][k] / it["grams"] * 100 if it["grams"] else 0) for k in it["nutrition"]}
            new_items.append({**it, "grams": g, "nutrition": nutrition_for(per100, g)})
    plan.items = new_items
    plan.totals = {k: round(sum(i["nutrition"][k] for i in new_items), 1) for k in ("kcal", "protein", "carbs", "fat", "fiber")}
    plan.status = MealPlanStatus.serving
    plan.served_at = now
    db.commit()
    db.refresh(plan)
    return plan_out(db, plan)


def stop(db: Session, user: User, plan_id: uuid.UUID) -> MealPlanOut:
    plan = _owned_plan(db, user, plan_id, lock=True)
    now = utcnow()
    for cmd in db.scalars(select(DispensingCommand).where(
            DispensingCommand.meal_plan_id == plan.id,
            DispensingCommand.status.in_((*ACTIVE_COMMAND_STATUSES, CommandStatus.queued)))
            .order_by(DispensingCommand.sequence).with_for_update(of=DispensingCommand)):
        if cmd.status in (CommandStatus.pending, CommandStatus.queued):
            cmd.status = CommandStatus.cancelled
            cmd.completed_at = now
            cmd.error_code = "meal_stopped_by_user"
            dispenser_service._log(db, cmd, "cancelled", "Meal stopped before this step started.")
        else:
            cmd.cancel_requested = True
            dispenser_service._log(db, cmd, "cancel_requested", "Meal stopped: closing and measuring.")
    db.flush()
    if plan.status == MealPlanStatus.proposed:
        plan.status = MealPlanStatus.cancelled
    else:
        dispenser_service._finalize_plan(db, plan)
    db.commit()
    db.refresh(plan)
    return plan_out(db, plan)
