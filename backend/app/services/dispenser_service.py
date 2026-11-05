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

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ConflictError, NotFoundError, ValidationFailedError
from app.models.device import Device, DeviceEvent, DispensingCommand, DispensingLog
from app.models.enums import (ACTIVE_COMMAND_STATUSES, TERMINAL_COMMAND_STATUSES, CommandStatus, CommandType,
                              EntrySource, MealType)
from app.models.meal import MealEntry
from app.models.user import User
from app.repositories import devices as device_repo
from app.schemas.device import (AckOut, CommandCreate, CommandLogOut, CommandOut, DeviceCommandOut,
                                DispenseSettings, ProgressIn, ProgressOut, ResultIn, ResultOut)
from app.services import meal_service
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
        elif cmd.status != CommandStatus.pending and _result_deadline(cmd) <= now:
            cmd.status = CommandStatus.failed
            cmd.completed_at = now
            cmd.error_code = "result_timeout"
            cmd.error_message = ("The dispenser stopped reporting before confirming a weight. "
                                 "Check the bowl; nothing was added to your log.")
            _log(db, cmd, "failed", cmd.error_message)
            db.add(DeviceEvent(device_id=device_id, event_type="command_timeout", severity="error",
                               message=f"No result received for command {cmd.id}.", data={}))


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

    from app.services.device_service import is_online, settings_of  # local import avoids a cycle
    if device.emergency_stop_active:
        raise ConflictError("Emergency stop is active. Reset it on the dispenser page before dispensing.",
                            code="emergency_stop_active")
    if device.registered_at is None:
        raise ConflictError("This dispenser has never connected. Flash the firmware with its token first.",
                            code="device_not_registered")
    if not is_online(device):
        raise ConflictError("The dispenser is offline. Check its power and Wi-Fi, then try again.",
                            code="device_offline")
    if not (device.hardware_info or {}).get("hx711_ready", False):
        raise ConflictError("The dispenser reports that its scale is not responding.", code="scale_not_ready")
    if not (device.hardware_info or {}).get("calibrated", False):
        raise ConflictError("The dispenser's scale is not calibrated yet.", code="scale_not_calibrated")
    if device_repo.active_command(db, device.id):
        raise ConflictError("The dispenser is busy with another request.", code="device_busy")

    dispense_settings: DispenseSettings = settings_of(device)
    params: dict = {"settings": dispense_settings.model_dump()}
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
        params.update(servo_channel=container.servo_channel, open_angle=container.open_angle,
                      closed_angle=container.closed_angle, container_label=container.label,
                      slot_number=container.slot_number)

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
    if cmd.status == CommandStatus.pending:
        cmd.status = CommandStatus.cancelled
        cmd.completed_at = utcnow()
        cmd.error_code = "cancelled_by_user"
        _log(db, cmd, "cancelled", "Cancelled before the dispenser started. Nothing was dispensed.")
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
    return DeviceCommandOut(
        command_id=cmd.id, type=cmd.command_type, target_weight_g=_f(cmd.target_weight_g),
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
        db.commit()
    if cmd.status == CommandStatus.pending and device.emergency_stop_active:
        cmd.status = CommandStatus.cancelled
        cmd.completed_at = utcnow()
        cmd.error_code = "emergency_stop"
        _log(db, cmd, "cancelled", "Emergency stop active; not executed.")
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
    device.device_state = "idle"
    db.commit()  # command result + meal entry + logs in one transaction
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
