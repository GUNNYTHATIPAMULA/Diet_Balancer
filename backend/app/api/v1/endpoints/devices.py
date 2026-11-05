"""Device endpoints.

Two audiences share the /devices prefix:
* the web app (JWT bearer token) manages devices and containers;
* the ESP32 (X-Device-Token header, never a user JWT) registers, sends heartbeats
  and pulls/acknowledges commands. The ESP32 always initiates the connection.
"""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import CurrentUser, DbSession, HeaderDevice, PathDevice, get_user_or_device
from app.core.rate_limit import rate_limit
from app.models.device import Device
from app.schemas.common import MessageOut
from app.schemas.device import (AckOut, ContainerCreate, ContainerOut, ContainerUpdate, DeviceCommandOut,
                                DeviceConfigOut, DeviceCreate, DeviceCreatedOut, DeviceEventOut, DeviceOut,
                                DeviceRegisterIn, DeviceUpdate, DispenseSettings, EmergencyStopIn, HeartbeatIn,
                                HeartbeatOut, ProgressIn, ProgressOut, ResultIn, ResultOut)
from app.services import device_service, dispenser_service

router = APIRouter(prefix="/devices", tags=["devices"])

# ---- ESP32 endpoints (static paths first) ----------------------------------------


@router.post("/register", response_model=DeviceConfigOut, tags=["device-api"],
             dependencies=[Depends(rate_limit("device_register", 20, 60))])
def register_device(data: DeviceRegisterIn, device: HeaderDevice, db: DbSession):
    return device_service.register_device(db, device, data)


@router.post("/heartbeat", response_model=HeartbeatOut, tags=["device-api"])
def heartbeat(data: HeartbeatIn, device: HeaderDevice, db: DbSession):
    return device_service.heartbeat(db, device, data)


@router.post("/{device_id}/heartbeat", response_model=HeartbeatOut, tags=["device-api"])
def heartbeat_by_path(data: HeartbeatIn, device: PathDevice, db: DbSession):
    return device_service.heartbeat(db, device, data)


@router.get("/{device_id}/commands/next", response_model=DeviceCommandOut, tags=["device-api"],
            responses={204: {"description": "No command waiting"}})
def next_command(device: PathDevice, db: DbSession):
    cmd = dispenser_service.next_command(db, device)
    if cmd is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return cmd


@router.post("/{device_id}/commands/{command_id}/ack", response_model=AckOut, tags=["device-api"])
def ack_command(command_id: uuid.UUID, device: PathDevice, db: DbSession):
    return dispenser_service.acknowledge(db, device, command_id)


@router.post("/{device_id}/commands/{command_id}/progress", response_model=ProgressOut, tags=["device-api"])
def command_progress(command_id: uuid.UUID, data: ProgressIn, device: PathDevice, db: DbSession):
    return dispenser_service.progress(db, device, command_id, data)


@router.post("/{device_id}/commands/{command_id}/result", response_model=ResultOut, tags=["device-api"])
def command_result(command_id: uuid.UUID, data: ResultIn, device: PathDevice, db: DbSession):
    return dispenser_service.submit_result(db, device, command_id, data)


@router.post("/{device_id}/emergency-stop", response_model=MessageOut, tags=["device-api"])
def emergency_stop(device_id: uuid.UUID, db: DbSession,
                   actor: Annotated[object, Depends(get_user_or_device)],
                   data: EmergencyStopIn | None = None):
    reason = data.reason if data else None
    if isinstance(actor, Device):
        device_service.emergency_stop(db, actor, source="device", reason=reason)
    else:
        device_service.user_emergency_stop(db, actor, device_id, reason)
    return MessageOut(message="Emergency stop is active. The dispenser will close and refuse new requests.")


# ---- Web app endpoints -------------------------------------------------------------


@router.get("", response_model=list[DeviceOut])
def list_devices(user: CurrentUser, db: DbSession):
    return device_service.list_devices(db, user)


@router.post("", response_model=DeviceCreatedOut, status_code=status.HTTP_201_CREATED)
def create_device(data: DeviceCreate, user: CurrentUser, db: DbSession):
    return device_service.create_device(db, user, data)


@router.get("/{device_id}", response_model=DeviceOut)
def get_device(device_id: uuid.UUID, user: CurrentUser, db: DbSession):
    return device_service.get_device(db, user, device_id)


@router.patch("/{device_id}", response_model=DeviceOut)
def update_device(device_id: uuid.UUID, data: DeviceUpdate, user: CurrentUser, db: DbSession):
    return device_service.update_device(db, user, device_id, data)


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_device(device_id: uuid.UUID, user: CurrentUser, db: DbSession):
    device_service.delete_device(db, user, device_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{device_id}/rotate-token", response_model=DeviceCreatedOut)
def rotate_token(device_id: uuid.UUID, user: CurrentUser, db: DbSession):
    return device_service.rotate_token(db, user, device_id)


@router.put("/{device_id}/settings", response_model=DeviceOut)
def update_settings(device_id: uuid.UUID, data: DispenseSettings, user: CurrentUser, db: DbSession):
    return device_service.update_settings(db, user, device_id, data)


@router.post("/{device_id}/emergency-stop/reset", response_model=DeviceOut)
def reset_emergency_stop(device_id: uuid.UUID, user: CurrentUser, db: DbSession):
    return device_service.reset_emergency_stop(db, user, device_id)


@router.get("/{device_id}/events", response_model=list[DeviceEventOut])
def list_events(device_id: uuid.UUID, user: CurrentUser, db: DbSession, limit: int = Query(30, ge=1, le=200)):
    return device_service.list_events(db, user, device_id, limit)


@router.post("/{device_id}/containers", response_model=ContainerOut, status_code=status.HTTP_201_CREATED)
def add_container(device_id: uuid.UUID, data: ContainerCreate, user: CurrentUser, db: DbSession):
    return device_service.add_container(db, user, device_id, data)


@router.patch("/{device_id}/containers/{container_id}", response_model=ContainerOut)
def update_container(device_id: uuid.UUID, container_id: uuid.UUID, data: ContainerUpdate, user: CurrentUser,
                     db: DbSession):
    return device_service.update_container(db, user, device_id, container_id, data)


@router.delete("/{device_id}/containers/{container_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_container(device_id: uuid.UUID, container_id: uuid.UUID, user: CurrentUser, db: DbSession):
    device_service.delete_container(db, user, device_id, container_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
