import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.device import Device, DeviceContainer, DispensingCommand
from app.models.enums import ACTIVE_COMMAND_STATUSES


def get_owned(db: Session, device_id: uuid.UUID, user_id: uuid.UUID) -> Device | None:
    return db.scalar(select(Device).where(Device.id == device_id, Device.owner_user_id == user_id))


def list_owned(db: Session, user_id: uuid.UUID) -> list[Device]:
    return list(db.scalars(select(Device).where(Device.owner_user_id == user_id).order_by(Device.created_at)))


def get_container(db: Session, device_id: uuid.UUID, container_id: uuid.UUID) -> DeviceContainer | None:
    return db.scalar(select(DeviceContainer).where(DeviceContainer.id == container_id,
                                                   DeviceContainer.device_id == device_id))


def active_command(db: Session, device_id: uuid.UUID, *, lock: bool = False) -> DispensingCommand | None:
    stmt = select(DispensingCommand).where(DispensingCommand.device_id == device_id,
                                           DispensingCommand.status.in_(ACTIVE_COMMAND_STATUSES))
    if lock:
        stmt = stmt.with_for_update(of=DispensingCommand)
    return db.scalar(stmt)
