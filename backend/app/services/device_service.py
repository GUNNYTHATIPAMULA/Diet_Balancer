"""Device management (user side) and device authentication/registration/heartbeat (ESP32 side)."""
import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ConflictError, NotFoundError, UnauthorizedError, ValidationFailedError
from app.core.security import device_token_matches, generate_device_token, hash_device_token
from app.models.device import Device, DeviceContainer, DeviceEvent, DispensingCommand, DispensingLog
from app.models.enums import ACTIVE_COMMAND_STATUSES, CommandStatus
from app.models.user import User
from app.repositories import devices as device_repo
from app.repositories import foods as food_repo
from app.schemas.device import (ContainerCreate, ContainerFood, ContainerOut, ContainerUpdate, DeviceConfigOut,
                                DeviceCreate, DeviceCreatedOut, DeviceEventOut, DeviceOut, DeviceRegisterIn,
                                DeviceUpdate, DispenseSettings, HeartbeatIn, HeartbeatOut)
from app.services import dispenser_service
from app.utils.time import as_utc, utcnow


def add_event(db: Session, device: Device, event_type: str, message: str, severity: str = "info",
              data: dict | None = None) -> None:
    db.add(DeviceEvent(device_id=device.id, event_type=event_type, severity=severity, message=message,
                       data=data or {}))


def is_online(device: Device) -> bool:
    seen = as_utc(device.last_heartbeat_at)
    return seen is not None and utcnow() - seen <= timedelta(seconds=get_settings().DEVICE_ONLINE_TIMEOUT_SECONDS)


def settings_of(device: Device) -> DispenseSettings:
    return DispenseSettings(**(device.dispense_settings or {}))


def container_out(c: DeviceContainer) -> ContainerOut:
    return ContainerOut(
        id=c.id, slot_number=c.slot_number, servo_channel=c.servo_channel, label=c.label,
        food=ContainerFood(id=c.food.id, name=c.food.name, calories_per_100g=float(c.food.calories_per_100g))
        if c.food else None,
        open_angle=c.open_angle, closed_angle=c.closed_angle,
        capacity_g=float(c.capacity_g) if c.capacity_g is not None else None,
        estimated_remaining_g=float(c.estimated_remaining_g) if c.estimated_remaining_g is not None else None,
        is_enabled=c.is_enabled,
    )


def device_out(db: Session, device: Device) -> DeviceOut:
    active = device_repo.active_command(db, device.id)
    return DeviceOut(
        id=device.id, name=device.name, hardware_id=device.hardware_id, token_hint=device.token_hint, is_online=is_online(device),
        is_registered=device.registered_at is not None, firmware_version=device.firmware_version,
        hardware_info=device.hardware_info or {}, ip_address=device.ip_address, wifi_rssi=device.wifi_rssi,
        device_state=device.device_state,
        last_weight_g=float(device.last_weight_g) if device.last_weight_g is not None else None,
        last_heartbeat_at=device.last_heartbeat_at, registered_at=device.registered_at,
        emergency_stop_active=device.emergency_stop_active, dispense_settings=settings_of(device),
        containers=[container_out(c) for c in device.containers],
        active_command_id=active.id if active else None, created_at=device.created_at,
    )


def _owned(db: Session, user: User, device_id: uuid.UUID) -> Device:
    device = device_repo.get_owned(db, device_id, user.id)
    if device is None:
        raise NotFoundError("Device not found.")
    return device


# ---- User-facing ---------------------------------------------------------------

def list_devices(db: Session, user: User) -> list[DeviceOut]:
    devices = device_repo.list_owned(db, user.id)
    for d in devices:
        dispenser_service.expire_stale(db, d.id)
    db.commit()
    return [device_out(db, d) for d in devices]


def get_device(db: Session, user: User, device_id: uuid.UUID) -> DeviceOut:
    device = _owned(db, user, device_id)
    dispenser_service.expire_stale(db, device.id)
    db.commit()
    return device_out(db, device)


def create_device(db: Session, user: User, data: DeviceCreate) -> DeviceCreatedOut:
    token = generate_device_token()
    device = Device(owner_user_id=user.id, name=data.name.strip(), token_hash=hash_device_token(token),
                    token_hint=token[-4:], dispense_settings=DispenseSettings().model_dump())
    db.add(device)
    db.flush()
    add_event(db, device, "created", f"Device '{device.name}' added.")
    db.commit()
    db.refresh(device)
    return DeviceCreatedOut(
        device=device_out(db, device), device_token=token,
        note="Copy this token into hardware/esp32/include/secrets.h now. It is shown only once.",
    )


def update_device(db: Session, user: User, device_id: uuid.UUID, data: DeviceUpdate) -> DeviceOut:
    device = _owned(db, user, device_id)
    device.name = data.name.strip()
    db.commit()
    return device_out(db, device)


def delete_device(db: Session, user: User, device_id: uuid.UUID) -> None:
    device = _owned(db, user, device_id)
    if device_repo.active_command(db, device.id):
        raise ConflictError("Wait for the current dispense to finish (or stop it) before removing the device.",
                            code="device_busy")
    db.delete(device)
    db.commit()


def rotate_token(db: Session, user: User, device_id: uuid.UUID) -> DeviceCreatedOut:
    device = _owned(db, user, device_id)
    token = generate_device_token()
    device.token_hash = hash_device_token(token)
    device.token_hint = token[-4:]
    add_event(db, device, "token_rotated", "Device token replaced. The old token no longer works.", "warning")
    db.commit()
    return DeviceCreatedOut(device=device_out(db, device), device_token=token,
                            note="Update DEVICE_TOKEN in secrets.h and re-flash the ESP32. Shown only once.")


def update_settings(db: Session, user: User, device_id: uuid.UUID, data: DispenseSettings) -> DeviceOut:
    device = _owned(db, user, device_id)
    device.dispense_settings = data.model_dump()
    add_event(db, device, "settings_updated", "Dispensing settings updated.", data=data.model_dump())
    db.commit()
    return device_out(db, device)


def _check_servo_channel(device: Device, channel: int) -> None:
    servo_count = (device.hardware_info or {}).get("servo_count")
    if servo_count is not None and channel >= servo_count:
        raise ValidationFailedError(
            f"This device reports {servo_count} servo(s), so use channel 0 to {servo_count - 1}.",
            code="invalid_servo_channel")


def add_container(db: Session, user: User, device_id: uuid.UUID, data: ContainerCreate) -> ContainerOut:
    device = _owned(db, user, device_id)
    _check_servo_channel(device, data.servo_channel)
    if data.food_item_id and food_repo.get_visible(db, data.food_item_id, user.id) is None:
        raise ValidationFailedError("Choose a food from the list.", code="unknown_food")
    container = DeviceContainer(device_id=device.id, **data.model_dump())
    db.add(container)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise ConflictError("That slot number or servo channel is already used on this device.",
                            code="container_conflict")
    add_event(db, device, "container_added",
              f"Container {data.slot_number} ({data.label}) mapped to servo channel {data.servo_channel}.")
    db.commit()
    db.refresh(container)
    return container_out(container)


def update_container(db: Session, user: User, device_id: uuid.UUID, container_id: uuid.UUID,
                     data: ContainerUpdate) -> ContainerOut:
    device = _owned(db, user, device_id)
    container = device_repo.get_container(db, device.id, container_id)
    if container is None:
        raise NotFoundError("Container not found.")
    if device_repo.active_command(db, device.id):
        raise ConflictError("Container settings can't change while the device is dispensing.", code="device_busy")
    changes = data.model_dump(exclude_unset=True, exclude={"clear_food"})
    if "servo_channel" in changes and changes["servo_channel"] is not None:
        _check_servo_channel(device, changes["servo_channel"])
    if changes.get("food_item_id") and food_repo.get_visible(db, changes["food_item_id"], user.id) is None:
        raise ValidationFailedError("Choose a food from the list.", code="unknown_food")
    for key, value in changes.items():
        if value is not None:
            setattr(container, key, value)
    if data.clear_food:
        container.food_item_id = None
    if "capacity_g" in data.model_fields_set and data.capacity_g is None:
        container.capacity_g = None
    if "estimated_remaining_g" in data.model_fields_set and data.estimated_remaining_g is None:
        container.estimated_remaining_g = None
    if container.open_angle == container.closed_angle:
        raise ValidationFailedError("Open and closed angles must be different.")
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise ConflictError("That servo channel is already used by another container.", code="container_conflict")
    db.commit()
    db.refresh(container)
    return container_out(container)


def delete_container(db: Session, user: User, device_id: uuid.UUID, container_id: uuid.UUID) -> None:
    device = _owned(db, user, device_id)
    container = device_repo.get_container(db, device.id, container_id)
    if container is None:
        raise NotFoundError("Container not found.")
    if device_repo.active_command(db, device.id):
        raise ConflictError("Containers can't be removed while the device is dispensing.", code="device_busy")
    db.delete(container)
    db.commit()


def list_events(db: Session, user: User, device_id: uuid.UUID, limit: int) -> list[DeviceEventOut]:
    device = _owned(db, user, device_id)
    events = db.scalars(select(DeviceEvent).where(DeviceEvent.device_id == device.id)
                        .order_by(DeviceEvent.created_at.desc()).limit(limit))
    return [DeviceEventOut(id=e.id, event_type=e.event_type, severity=e.severity, message=e.message,
                           data=e.data or {}, created_at=e.created_at) for e in events]


def emergency_stop(db: Session, device: Device, *, source: str, reason: str | None) -> None:
    """Latch the stop flag, cancel queued work, and ask any running command to abort."""
    device.emergency_stop_active = True
    for cmd in db.scalars(select(DispensingCommand).where(
            DispensingCommand.device_id == device.id,
            DispensingCommand.status.in_(ACTIVE_COMMAND_STATUSES)).with_for_update(of=DispensingCommand)):
        if cmd.status == CommandStatus.pending:
            cmd.status = CommandStatus.cancelled
            cmd.completed_at = utcnow()
            cmd.error_code = "emergency_stop"
            db.add(DispensingLog(command_id=cmd.id, event="cancelled", status="cancelled",
                                 message="Cancelled by emergency stop before the device started."))
        else:
            cmd.cancel_requested = True
            db.add(DispensingLog(command_id=cmd.id, event="cancel_requested", status=cmd.status.value,
                                 message="Emergency stop requested."))
    add_event(db, device, "emergency_stop", f"Emergency stop from {source}." + (f" {reason}" if reason else ""),
              "error", {"source": source})
    db.commit()


def user_emergency_stop(db: Session, user: User, device_id: uuid.UUID, reason: str | None) -> DeviceOut:
    device = _owned(db, user, device_id)
    emergency_stop(db, device, source="web app", reason=reason)
    return device_out(db, device)


def reset_emergency_stop(db: Session, user: User, device_id: uuid.UUID) -> DeviceOut:
    device = _owned(db, user, device_id)
    if device_repo.active_command(db, device.id):
        raise ConflictError("The device is still finishing the stopped command. Try again in a few seconds.",
                            code="device_busy")
    device.emergency_stop_active = False
    add_event(db, device, "emergency_stop_reset", "Emergency stop cleared from the web app.", "warning")
    db.commit()
    return device_out(db, device)


# ---- Device-facing ---------------------------------------------------------------

def authenticate_device(db: Session, device_id: uuid.UUID | None, token: str | None) -> Device:
    if device_id is None or not token:
        raise UnauthorizedError("Device credentials missing.", code="device_auth_required")
    device = db.get(Device, device_id)
    if device is None or not device_token_matches(token, device.token_hash):
        raise UnauthorizedError("Device credentials are invalid.", code="device_auth_failed")
    return device


def device_config(device: Device) -> DeviceConfigOut:
    return DeviceConfigOut(
        device_id=device.id, name=device.name, emergency_stop_active=device.emergency_stop_active,
        containers=[{"slot_number": c.slot_number, "servo_channel": c.servo_channel, "label": c.label,
                     "open_angle": c.open_angle, "closed_angle": c.closed_angle, "enabled": c.is_enabled}
                    for c in device.containers],
        dispense_settings=settings_of(device), server_time=utcnow(),
    )


def register_device(db: Session, device: Device, data: DeviceRegisterIn) -> DeviceConfigOut:
    now = utcnow()
    first = device.registered_at is None
    device.registered_at = device.registered_at or now
    device.last_heartbeat_at = now
    device.firmware_version = data.firmware_version
    device.ip_address = data.ip_address
    device.wifi_rssi = data.wifi_rssi
    device.device_state = "idle"
    device.hardware_info = {"servo_count": data.servo_count, "hx711_ready": data.hx711_ready,
                            "oled_ready": data.oled_ready, "calibrated": data.calibrated}
    add_event(db, device, "registered" if first else "rebooted",
              f"Firmware {data.firmware_version} connected"
              + (f" (reset reason: {data.reset_reason})." if data.reset_reason else "."),
              "info" if data.hx711_ready and data.calibrated else "warning", device.hardware_info)
    if not data.hx711_ready:
        add_event(db, device, "sensor_error", "Load cell (HX711) not responding at boot.", "error")
    if not data.calibrated:
        add_event(db, device, "not_calibrated", "Scale calibration factor is not set; dispensing is disabled "
                                                "on the device until it is calibrated.", "warning")
    if data.interrupted_command_id:
        dispenser_service.fail_interrupted(db, device, data.interrupted_command_id)
    from app.services import pairing_service  # local import avoids a cycle
    pairing_service.mark_delivered(db, device)
    db.commit()
    return device_config(device)


def heartbeat(db: Session, device: Device, data: HeartbeatIn) -> HeartbeatOut:
    device.last_heartbeat_at = utcnow()
    device.device_state = data.state
    if data.weight_g is not None:
        device.last_weight_g = round(data.weight_g, 1)
    if data.wifi_rssi is not None:
        device.wifi_rssi = data.wifi_rssi
    if data.ip_address:
        device.ip_address = data.ip_address
    if data.hx711_ready is not None:
        info = dict(device.hardware_info or {})
        if info.get("hx711_ready") and not data.hx711_ready:
            add_event(db, device, "sensor_error", "Load cell (HX711) stopped responding.", "error")
        info["hx711_ready"] = data.hx711_ready
        device.hardware_info = info
    if data.last_error and data.state == "error":
        add_event(db, device, "device_error", data.last_error, "error")
    dispenser_service.expire_stale(db, device.id)
    has_pending = db.scalar(select(DispensingCommand.id).where(
        DispensingCommand.device_id == device.id, DispensingCommand.status == CommandStatus.pending)) is not None
    db.commit()
    return HeartbeatOut(server_time=utcnow(), emergency_stop_active=device.emergency_stop_active,
                        has_pending_command=has_pending)
