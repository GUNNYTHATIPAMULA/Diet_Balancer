"""Dispensing command lifecycle.

    pending --ack--> acknowledged --progress--> dispensing --result--> completed | failed | cancelled
    pending --(not picked up in time)--> expired
    pending --(user cancel / emergency stop)--> cancelled
    acknowledged/dispensing --(no result in time)--> failed (result_timeout)

Safety rules implemented here:
* A meal entry is created only for a *completed* result, using the weight the load
  cell measured, inside the same transaction that closes the command.
* A command is never handed to the device after it expires, so a device that
  reconnects later cannot dispense a stale request.
* Retried acks/results are idempotent: they return the stored outcome and never
  create a second meal entry (meal_entries.dispensing_command_id is UNIQUE).
"""
import uuid
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ConflictError, NotFoundError, ValidationFailedError
from app.models.device import Device, DeviceContainer, DeviceEvent, DispensingCommand, DispensingLog, MealPlan
from app.models.enums import (ACTIVE_COMMAND_STATUSES, TERMINAL_COMMAND_STATUSES, CommandStatus, CommandType,
                              EntrySource, MealPlanStatus, MealType)
from app.models.meal import MealEntry
from app.models.user import User
from app.repositories import devices as device_repo
from app.schemas.device import (AckOut, CommandCreate, CommandLogOut, CommandOut, DeviceCommandOut,
                                DispenseSettings, ProgressIn, ProgressOut, ResultIn, ResultOut)
from app.services import meal_service
from app.services.nutrition_calculator import food_per_100g, scale_nutrition
from app.utils.time import as_utc, utcnow

MIN_CONFIRMED_WEIGHT_G = 0.5   # below this the load cell has not confirmed any food
LATE_RESULT_WINDOW = timedelta(minutes=10)


def _log(db: Session, cmd: DispensingCommand, event: str, message: str | None = None,
         weight: float | None = None) -> None:
    db.add(DispensingLog(command_id=cmd.id, event=event, status=cmd.status.value, weight_g=weight,
                         message=message))


def _f(value) -> float | None:
    return float(value) if value is not None else None


def _meal_entry_id(db: Session, cmd: DispensingCommand) -> uuid.UUID | None:
    return db.scalar(select(MealEntry.id).where(MealEntry.dispensing_command_id == cmd.id))


# Failures that mean the hardware or link is not trustworthy: stop the rest of a meal.
# Others (empty/jammed container, under target) only affect that one food.
MEAL_STOP_CODES = {"emergency_stop", "sensor_timeout", "sensor_implausible", "bowl_removed", "sensor_not_ready",
                   "not_calibrated", "device_rebooted", "result_timeout", "not_picked_up", "unstable_scale",
                   "invalid_servo", "invalid_angles"}


def has_queued(db: Session, device_id: uuid.UUID) -> bool:
    return db.scalar(select(DispensingCommand.id).where(DispensingCommand.device_id == device_id,
                                                        DispensingCommand.status == CommandStatus.queued)) is not None


def ascii_label(text: str | None, limit: int = 21) -> str:
    """Short ASCII name for the OLED (21 characters fit on one line): 'Pōha' -> 'Poha'.
    Long names drop bracketed details first: 'Soya chunks (dry) extra' -> 'Soya chunks extra'."""
    import re
    import unicodedata
    if not text:
        return ""
    label = " ".join(unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().split())
    if len(label) > limit:
        label = " ".join(re.sub(r"\s*\([^)]*\)", "", label).split())
    return label[:limit].rstrip(" ,")


def accuracy(cmd: DispensingCommand) -> dict:
    """Compare the MEASURED weight with the target using the tolerance sent with the command."""
    if cmd.command_type != CommandType.dispense or cmd.target_weight_g is None or cmd.dispensed_weight_g is None:
        return {}
    s = (cmd.parameters or {}).get("settings", {})
    pct = float(s.get("tolerance_percent", get_settings().DISPENSE_TOLERANCE_PERCENT))
    target, measured = float(cmd.target_weight_g), float(cmd.dispensed_weight_g)
    tol = max(target * pct / 100.0, float(s.get("tolerance_g", 3)))
    diff = measured - target
    status = "within_tolerance" if abs(diff) <= tol else ("over" if diff > 0 else "under")
    return {"tolerance_percent": pct, "tolerance_g": round(tol, 1), "difference_g": round(diff, 1),
            "difference_percent": round(diff / target * 100.0, 1) if target else None, "accuracy": status}


def measured_nutrition(cmd: DispensingCommand) -> dict | None:
    measured = _f(cmd.dispensed_weight_g)
    if not measured or measured <= 0 or cmd.food is None:
        return None
    n = scale_nutrition(food_per_100g(cmd.food), measured)
    return {"calories": round(n["calories"], 1), "protein_g": round(n["protein_g"], 1),
            "carbs_g": round(n["carbs_g"], 1), "fat_g": round(n["fat_g"], 1), "fiber_g": round(n["fiber_g"], 1)}


def build_params(container: DeviceContainer | None, dispense_settings: DispenseSettings) -> dict:
    settings = dispense_settings.model_dump()
    params: dict = {"settings": settings}
    if container is not None:
        if dispense_settings.auto_tune_inflight and container.inflight_g is not None:
            settings["inflight_g"] = float(container.inflight_g)  # learned for this container
        params.update(servo_channel=container.servo_channel, open_angle=container.open_angle,
                      closed_angle=container.closed_angle, container_label=container.label,
                      slot_number=container.slot_number, inflight_g_used=settings["inflight_g"],
                      label=ascii_label(container.food.name if container.food else container.label))
    return params


def check_device_ready(db: Session, device: Device) -> None:
    from app.services.device_service import is_online  # local import avoids a cycle
    if device.emergency_stop_active:
        raise ConflictError("Emergency stop is active. Reset it on the dispenser page before dispensing.",
                            code="emergency_stop_active")
    if device.registered_at is None:
        raise ConflictError("This dispenser has never connected. Pair it first.", code="device_not_registered")
    if not is_online(device):
        raise ConflictError("The dispenser is offline. Check its power and Wi-Fi, then try again.",
                            code="device_offline")
    if not (device.hardware_info or {}).get("hx711_ready", False):
        raise ConflictError("The dispenser reports that its scale is not responding.", code="scale_not_ready")
    if not (device.hardware_info or {}).get("calibrated", False):
        raise ConflictError("The dispenser's scale is not calibrated yet.", code="scale_not_calibrated")
    if device_repo.active_command(db, device.id) or has_queued(db, device.id):
        raise ConflictError("The dispenser is busy with another request.", code="device_busy")


def _auto_tune(db: Session, cmd: DispensingCommand) -> None:
    """Learn how much food keeps falling after the gate closes, per container."""
    params = cmd.parameters or {}
    if not params.get("settings", {}).get("auto_tune_inflight", True) or cmd.container is None:
        return
    measured, target = _f(cmd.dispensed_weight_g), _f(cmd.target_weight_g)
    used = params.get("inflight_g_used")
    if measured is None or target is None or used is None:
        return
    error = measured - target
    if abs(error) < 1.0:
        return
    new = round(min(max(float(used) + 0.5 * error, 0.0), 60.0), 1)
    if cmd.container.food_item_id != cmd.food_item_id or abs(new - float(used)) < 0.5:
        return
    cmd.container.inflight_g = new
    db.add(DeviceEvent(device_id=cmd.device_id, event_type="auto_tune", severity="info",
                       message=(f"{cmd.container.label}: measured {measured:.0f} g for {target:.0f} g, so it now closes "
                                f"{new:g} g early (was {float(used):g} g)."), data={"inflight_g": new}))


def _finalize_plan(db: Session, plan: MealPlan) -> None:
    cmds = list(db.scalars(select(DispensingCommand).where(DispensingCommand.meal_plan_id == plan.id)))
    if any(c.status not in TERMINAL_COMMAND_STATUSES for c in cmds):
        return
    done = [c for c in cmds if c.status == CommandStatus.completed]
    if cmds and len(done) == len(cmds):
        plan.status = MealPlanStatus.completed
    elif done:
        plan.status = MealPlanStatus.partial
    elif any(c.error_code in ("cancelled_by_user", "meal_stopped_by_user") for c in cmds):
        plan.status = MealPlanStatus.cancelled
    else:
        plan.status = MealPlanStatus.failed


def _on_terminal(db: Session, cmd: DispensingCommand) -> None:
    """Call whenever a command reaches a final status: advances or stops a meal."""
    db.flush()  # the finished command must be written before the next one becomes pending
    if cmd.meal_plan_id is None:
        return
    plan = db.get(MealPlan, cmd.meal_plan_id)
    queued = list(db.scalars(select(DispensingCommand).where(
        DispensingCommand.meal_plan_id == cmd.meal_plan_id, DispensingCommand.status == CommandStatus.queued)
        .order_by(DispensingCommand.sequence).with_for_update(of=DispensingCommand)))
    device = db.get(Device, cmd.device_id)
    stop = (cmd.status in (CommandStatus.cancelled, CommandStatus.expired)
            or (cmd.status == CommandStatus.failed and cmd.error_code in MEAL_STOP_CODES)
            or device.emergency_stop_active)
    now = utcnow()
    if stop:
        for q in queued:
            q.status = CommandStatus.cancelled
            q.completed_at = now
            q.error_code = "meal_stopped"
            q.error_message = "Not dispensed because an earlier step of the meal stopped."
            _log(db, q, "cancelled", q.error_message)
    elif queued:
        nxt = queued[0]
        nxt.status = CommandStatus.pending
        nxt.expires_at = now + timedelta(seconds=get_settings().COMMAND_PENDING_TTL_SECONDS)
        _log(db, nxt, "next_in_meal", "Next item of your meal; waiting for the dispenser.")
    db.flush()
    if plan is not None:
        _finalize_plan(db, plan)


def command_out(db: Session, cmd: DispensingCommand, with_logs: bool = True) -> CommandOut:
    logs = []
    if with_logs:
        logs = [CommandLogOut(event=l.event, status=l.status, weight_g=_f(l.weight_g), message=l.message,
                              created_at=l.created_at)
                for l in db.scalars(select(DispensingLog).where(DispensingLog.command_id == cmd.id)
                                    .order_by(DispensingLog.created_at, DispensingLog.id))]
    return CommandOut(
        id=cmd.id, device_id=cmd.device_id, container_id=cmd.container_id,
        container_label=cmd.parameters.get("container_label") if cmd.parameters else None,
        food_item_id=cmd.food_item_id, food_name=cmd.food.name if cmd.food else None,
        command_type=cmd.command_type, status=cmd.status, target_weight_g=_f(cmd.target_weight_g),
        dispensed_weight_g=_f(cmd.dispensed_weight_g), start_weight_g=_f(cmd.start_weight_g),
        final_weight_g=_f(cmd.final_weight_g), last_progress_weight_g=_f(cmd.last_progress_weight_g),
        meal_type=cmd.meal_type, consumed_on=cmd.consumed_on, log_to_meals=cmd.log_to_meals,
        cancel_requested=cmd.cancel_requested, error_code=cmd.error_code, error_message=cmd.error_message,
        duration_ms=cmd.duration_ms, meal_entry_id=_meal_entry_id(db, cmd), created_at=cmd.created_at,
        acknowledged_at=cmd.acknowledged_at, completed_at=cmd.completed_at, expires_at=cmd.expires_at, logs=logs,
        meal_plan_id=cmd.meal_plan_id, sequence=cmd.sequence, nutrition=measured_nutrition(cmd), **accuracy(cmd),
    )


def _result_deadline(cmd: DispensingCommand):
    max_ms = (cmd.parameters or {}).get("settings", {}).get("max_duration_ms", 120000)
    start = as_utc(cmd.acknowledged_at) or as_utc(cmd.created_at)
    return start + timedelta(milliseconds=max_ms, seconds=get_settings().COMMAND_RESULT_GRACE_SECONDS)


def expire_stale(db: Session, device_id: uuid.UUID) -> None:
    """Close commands the device never picked up or never finished. Caller commits."""
    now = utcnow()
    for cmd in db.scalars(select(DispensingCommand).where(
            DispensingCommand.device_id == device_id,
            DispensingCommand.status.in_(ACTIVE_COMMAND_STATUSES)).with_for_update(skip_locked=True, of=DispensingCommand)):
        if cmd.status == CommandStatus.pending and as_utc(cmd.expires_at) <= now:
            cmd.status = CommandStatus.expired
            cmd.completed_at = now
            cmd.error_code = "not_picked_up"
            cmd.error_message = "The dispenser did not pick up this request in time. Nothing was dispensed."
            _log(db, cmd, "expired", cmd.error_message)
            _on_terminal(db, cmd)
        elif cmd.status != CommandStatus.pending and _result_deadline(cmd) <= now:
            cmd.status = CommandStatus.failed
            cmd.completed_at = now
            cmd.error_code = "result_timeout"
            cmd.error_message = ("The dispenser stopped reporting before confirming a weight. "
                                 "Check the bowl; nothing was added to your log.")
            _log(db, cmd, "failed", cmd.error_message)
            db.add(DeviceEvent(device_id=device_id, event_type="command_timeout", severity="error",
                               message=f"No result received for command {cmd.id}.", data={}))
            _on_terminal(db, cmd)


# ---- User side -------------------------------------------------------------------

def create_command(db: Session, user: User, data: CommandCreate, idempotency_key: str | None) -> CommandOut:
    settings = get_settings()
    key = (idempotency_key or uuid.uuid4().hex).strip()
    if not 8 <= len(key) <= 64:
        raise ValidationFailedError("Idempotency-Key must be 8 to 64 characters.", code="bad_idempotency_key")

    existing = db.scalar(select(DispensingCommand).where(DispensingCommand.user_id == user.id,
                                                         DispensingCommand.idempotency_key == key))
    if existing:
        return command_out(db, existing)

    device = device_repo.get_owned(db, data.device_id, user.id)
    if device is None:
        raise NotFoundError("Device not found.")
    expire_stale(db, device.id)
    db.flush()

    from app.services.device_service import settings_of  # local import avoids a cycle
    check_device_ready(db, device)

    dispense_settings: DispenseSettings = settings_of(device)
    container = None
    if data.command_type == CommandType.dispense:
        container = device_repo.get_container(db, device.id, data.container_id)
        if container is None:
            raise ValidationFailedError("Choose a container on this dispenser.", code="unknown_container")
        if not container.is_enabled:
            raise ValidationFailedError(f"{container.label} is disabled.", code="container_disabled")
        if not settings.DISPENSE_MIN_G <= data.target_weight_g <= settings.DISPENSE_MAX_G:
            raise ValidationFailedError(
                f"Enter an amount between {settings.DISPENSE_MIN_G:g} g and {settings.DISPENSE_MAX_G:g} g.",
                code="target_out_of_range")
        if data.log_to_meals and container.food_item_id is None:
            raise ValidationFailedError(f"Assign a food to {container.label} so it can be added to your log.",
                                        code="container_without_food")
    params = build_params(container, dispense_settings)

    now = utcnow()
    cmd = DispensingCommand(
        device_id=device.id, user_id=user.id, container_id=container.id if container else None,
        food_item_id=container.food_item_id if container else None, command_type=data.command_type,
        status=CommandStatus.pending, idempotency_key=key,
        target_weight_g=data.target_weight_g if data.command_type == CommandType.dispense else None,
        meal_type=data.meal_type, consumed_on=data.consumed_on or date.today(),
        log_to_meals=data.log_to_meals and data.command_type == CommandType.dispense, parameters=params,
        created_at=now, expires_at=now + timedelta(seconds=settings.COMMAND_PENDING_TTL_SECONDS),
    )
    db.add(cmd)
    try:
        db.flush()
        _log(db, cmd, "created", "Waiting for the dispenser to pick up the request.",
             _f(cmd.target_weight_g))
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(DispensingCommand).where(DispensingCommand.user_id == user.id,
                                                             DispensingCommand.idempotency_key == key))
        if existing:
            return command_out(db, existing)
        raise ConflictError("The dispenser is busy with another request.", code="device_busy")
    db.refresh(cmd)
    return command_out(db, cmd)


def _owned_command(db: Session, user: User, command_id: uuid.UUID, lock: bool = False) -> DispensingCommand:
    stmt = select(DispensingCommand).where(DispensingCommand.id == command_id, DispensingCommand.user_id == user.id)
    if lock:
        stmt = stmt.with_for_update(of=DispensingCommand)
    cmd = db.scalar(stmt)
    if cmd is None:
        raise NotFoundError("Dispense request not found.")
    return cmd


def get_command(db: Session, user: User, command_id: uuid.UUID) -> CommandOut:
    cmd = _owned_command(db, user, command_id)
    expire_stale(db, cmd.device_id)
    db.commit()
    db.refresh(cmd)
    return command_out(db, cmd)


def list_commands(db: Session, user: User, device_id: uuid.UUID | None, limit: int) -> list[CommandOut]:
    stmt = select(DispensingCommand).where(DispensingCommand.user_id == user.id)
    if device_id:
        stmt = stmt.where(DispensingCommand.device_id == device_id)
    cmds = db.scalars(stmt.order_by(DispensingCommand.created_at.desc()).limit(limit)).unique()
    return [command_out(db, c, with_logs=False) for c in cmds]


def cancel_command(db: Session, user: User, command_id: uuid.UUID) -> CommandOut:
    cmd = _owned_command(db, user, command_id, lock=True)
    if cmd.status in TERMINAL_COMMAND_STATUSES:
        raise ConflictError("This request has already finished.", code="command_finished")
    if cmd.status in (CommandStatus.pending, CommandStatus.queued):
        cmd.status = CommandStatus.cancelled
        cmd.completed_at = utcnow()
        cmd.error_code = "cancelled_by_user"
        _log(db, cmd, "cancelled", "Cancelled before the dispenser started. Nothing was dispensed.")
        _on_terminal(db, cmd)
    else:
        cmd.cancel_requested = True
        _log(db, cmd, "cancel_requested", "Stop requested. The dispenser will close and report the measured weight.")
    db.commit()
    return command_out(db, cmd)


def log_measured(db: Session, user: User, command_id: uuid.UUID, meal_type: MealType | None) -> CommandOut:
    """Let the user explicitly log food that was measured by a stopped/failed dispense."""
    cmd = _owned_command(db, user, command_id, lock=True)
    if cmd.status not in (CommandStatus.failed, CommandStatus.cancelled):
        raise ConflictError("Only stopped or failed dispenses can be logged this way.", code="not_applicable")
    measured = _f(cmd.dispensed_weight_g)
    if measured is None or measured < MIN_CONFIRMED_WEIGHT_G:
        raise ConflictError("The scale did not confirm any dispensed food for this request.",
                            code="no_measured_weight")
    if cmd.food is None:
        raise ConflictError("This container had no food assigned.", code="container_without_food")
    if _meal_entry_id(db, cmd):
        raise ConflictError("This dispense is already in your log.", code="already_logged")
    entry = meal_service.build_entry(
        user_id=user.id, food=cmd.food, meal_type=meal_type or cmd.meal_type or MealType.snacks,
        quantity_g=round(measured, 1), consumed_on=cmd.consumed_on or date.today(),
        source=EntrySource.dispenser, dispensing_command_id=cmd.id)
    db.add(entry)
    _log(db, cmd, "logged_to_meals", f"{measured:.1f} g (measured) added to your log by you.", measured)
    db.commit()
    return command_out(db, cmd)


# ---- Device side -----------------------------------------------------------------

def _device_command(db: Session, device: Device, command_id: uuid.UUID) -> DispensingCommand:
    cmd = db.scalar(select(DispensingCommand).where(DispensingCommand.id == command_id,
                                                    DispensingCommand.device_id == device.id)
                    .with_for_update(of=DispensingCommand))
    if cmd is None:
        raise NotFoundError("Command not found for this device.")
    return cmd


def next_command(db: Session, device: Device) -> DeviceCommandOut | None:
    now = utcnow()
    seen = as_utc(device.last_heartbeat_at)
    if seen is None or now - seen > timedelta(seconds=5):
        device.last_heartbeat_at = now
    expire_stale(db, device.id)
    db.commit()
    if device.emergency_stop_active:
        return None
    cmd = db.scalar(select(DispensingCommand).where(
        DispensingCommand.device_id == device.id, DispensingCommand.status == CommandStatus.pending,
        DispensingCommand.expires_at > now).order_by(DispensingCommand.created_at))
    if cmd is None:
        return None
    p = cmd.parameters or {}
    meal_total = None
    if cmd.meal_plan_id:
        meal_total = db.scalar(select(func.count(DispensingCommand.id))
                               .where(DispensingCommand.meal_plan_id == cmd.meal_plan_id))
    return DeviceCommandOut(
        command_id=cmd.id, type=cmd.command_type, target_weight_g=_f(cmd.target_weight_g),
        label=p.get("label") or None, meal_position=cmd.sequence if cmd.meal_plan_id else None, meal_total=meal_total,
        servo_channel=p.get("servo_channel"), open_angle=p.get("open_angle"), closed_angle=p.get("closed_angle"),
        settings=DispenseSettings(**p.get("settings", {})), expires_at=cmd.expires_at,
    )


def acknowledge(db: Session, device: Device, command_id: uuid.UUID) -> AckOut:
    cmd = _device_command(db, device, command_id)
    if cmd.status in (CommandStatus.acknowledged, CommandStatus.dispensing):
        db.commit()
        return AckOut(command_id=cmd.id, status=cmd.status, already_acknowledged=True,
                      abort=cmd.cancel_requested or device.emergency_stop_active)
    if cmd.status == CommandStatus.pending and as_utc(cmd.expires_at) <= utcnow():
        cmd.status = CommandStatus.expired
        cmd.completed_at = utcnow()
        cmd.error_code = "not_picked_up"
        _log(db, cmd, "expired", "Picked up too late; not executed.")
        _on_terminal(db, cmd)
        db.commit()
    if cmd.status == CommandStatus.pending and device.emergency_stop_active:
        cmd.status = CommandStatus.cancelled
        cmd.completed_at = utcnow()
        cmd.error_code = "emergency_stop"
        _log(db, cmd, "cancelled", "Emergency stop active; not executed.")
        _on_terminal(db, cmd)
        db.commit()
    if cmd.status != CommandStatus.pending:
        raise ConflictError("This command must not be executed.", code="command_not_executable",
                            details={"status": cmd.status.value})
    cmd.status = CommandStatus.acknowledged
    cmd.acknowledged_at = utcnow()
    _log(db, cmd, "acknowledged", "Dispenser accepted the request.")
    db.commit()
    return AckOut(command_id=cmd.id, status=cmd.status, already_acknowledged=False, abort=False)


def progress(db: Session, device: Device, command_id: uuid.UUID, data: ProgressIn) -> ProgressOut:
    cmd = _device_command(db, device, command_id)
    if cmd.status in TERMINAL_COMMAND_STATUSES or cmd.status == CommandStatus.pending:
        db.commit()
        return ProgressOut(abort=True, reason="command_closed")
    if cmd.status == CommandStatus.acknowledged:
        cmd.status = CommandStatus.dispensing
    cmd.last_progress_weight_g = round(data.weight_g, 1)
    _log(db, cmd, "progress", data.phase, round(data.weight_g, 1))
    device.last_heartbeat_at = utcnow()
    db.commit()
    if device.emergency_stop_active:
        return ProgressOut(abort=True, reason="emergency_stop")
    if cmd.cancel_requested:
        return ProgressOut(abort=True, reason="cancel_requested")
    return ProgressOut(abort=False, reason=None)


def submit_result(db: Session, device: Device, command_id: uuid.UUID, data: ResultIn) -> ResultOut:
    cmd = _device_command(db, device, command_id)
    late_result = (cmd.status == CommandStatus.failed and cmd.error_code == "result_timeout"
                   and cmd.completed_at is not None and utcnow() - as_utc(cmd.completed_at) < LATE_RESULT_WINDOW)
    if cmd.status in TERMINAL_COMMAND_STATUSES and not late_result:
        db.commit()
        return ResultOut(command_id=cmd.id, status=cmd.status, duplicate=True, meal_entry_id=_meal_entry_id(db, cmd))
    if cmd.status == CommandStatus.pending and cmd.acknowledged_at is None:
        cmd.acknowledged_at = utcnow()

    now = utcnow()
    cmd.start_weight_g = data.start_weight_g
    cmd.final_weight_g = data.final_weight_g
    cmd.dispensed_weight_g = round(data.dispensed_weight_g, 1) if data.dispensed_weight_g is not None else None
    cmd.duration_ms = data.duration_ms
    cmd.completed_at = now
    cmd.error_code = data.error_code
    cmd.error_message = data.error_message
    status = CommandStatus(data.status)
    measured = _f(cmd.dispensed_weight_g)

    if (cmd.command_type == CommandType.dispense and status == CommandStatus.completed
            and (measured is None or measured < MIN_CONFIRMED_WEIGHT_G)):
        status = CommandStatus.failed
        cmd.error_code = "no_weight_measured"
        cmd.error_message = "The device reported completion but the scale measured no food."
    cmd.status = status
    note = " (late result accepted)" if late_result else ""
    weight_text = f"{measured:.1f} g measured" if measured is not None else "no weight measured"
    acc = accuracy(cmd)
    if acc:
        label = {"within_tolerance": "within tolerance", "over": "OVER target", "under": "under target"}[acc["accuracy"]]
        weight_text += f" for {float(cmd.target_weight_g):g} g ({acc['difference_g']:+g} g, {label})"
    _log(db, cmd, status.value, f"{weight_text}{note}" + (f": {cmd.error_message}" if cmd.error_message else ""),
         measured)

    entry_id = None
    if cmd.command_type == CommandType.tare and status == CommandStatus.completed:
        device.last_weight_g = 0
    if cmd.command_type == CommandType.dispense:
        if measured and measured > 0 and cmd.container and cmd.container.estimated_remaining_g is not None:
            cmd.container.estimated_remaining_g = max(float(cmd.container.estimated_remaining_g) - measured, 0)
        if (status == CommandStatus.completed and cmd.log_to_meals and cmd.food is not None
                and _meal_entry_id(db, cmd) is None):
            entry = meal_service.build_entry(
                user_id=cmd.user_id, food=cmd.food, meal_type=cmd.meal_type or MealType.snacks,
                quantity_g=measured, consumed_on=cmd.consumed_on or date.today(), source=EntrySource.dispenser,
                dispensing_command_id=cmd.id)
            db.add(entry)
            db.flush()
            entry_id = entry.id
            _log(db, cmd, "logged_to_meals", f"{measured:.1f} g (measured) added to your log.", measured)
    if status != CommandStatus.completed:
        db.add(DeviceEvent(device_id=device.id, event_type=f"dispense_{status.value}",
                           severity="warning" if status == CommandStatus.cancelled else "error",
                           message=cmd.error_message or f"Dispense {status.value}.",
                           data={"command_id": str(cmd.id), "error_code": cmd.error_code}))
    if cmd.command_type == CommandType.dispense and status == CommandStatus.completed:
        _auto_tune(db, cmd)
    device.device_state = "idle"
    _on_terminal(db, cmd)  # starts the next item of a meal, or stops it after a safety failure
    db.commit()  # command result + meal entry + logs + next meal step in one transaction
    return ResultOut(command_id=cmd.id, status=cmd.status, duplicate=False,
                     meal_entry_id=entry_id or _meal_entry_id(db, cmd))


def fail_interrupted(db: Session, device: Device, command_id: uuid.UUID) -> None:
    """Called when a device reboots and reports it was in the middle of a command."""
    cmd = db.scalar(select(DispensingCommand).where(DispensingCommand.id == command_id,
                                                    DispensingCommand.device_id == device.id).with_for_update(of=DispensingCommand))
    if cmd is None or cmd.status in TERMINAL_COMMAND_STATUSES:
        return
    cmd.status = CommandStatus.failed
    cmd.completed_at = utcnow()
    cmd.error_code = "device_rebooted"
    cmd.error_message = "The dispenser restarted during this request. Check the bowl; nothing was logged."
    _log(db, cmd, "failed", cmd.error_message)
    db.add(DeviceEvent(device_id=device.id, event_type="dispense_failed", severity="error",
                       message=cmd.error_message, data={"command_id": str(cmd.id)}))
    _on_terminal(db, cmd)
