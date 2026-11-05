import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.device import DeviceOut


class AnnounceIn(BaseModel):
    hardware_id: str = Field(pattern=r"^[A-Za-z0-9-]{4,32}$")
    pairing_secret: str = Field(min_length=32, max_length=128)
    firmware_version: str = Field(max_length=40)
    servo_count: int = Field(ge=0, le=16)
    hx711_ready: bool
    oled_ready: bool
    calibrated: bool
    local_ip: str | None = Field(default=None, max_length=45)
    # The dispenser may choose its own code so it can show it on the OLED immediately.
    # The server keeps it if it is free, otherwise returns a different one to display.
    pairing_code: str | None = Field(default=None, pattern=r"^\d{6}$")
    device_name: str | None = Field(default=None, max_length=80)


class AnnounceOut(BaseModel):
    status: str                      # "waiting" or "paired"
    pairing_code: str | None = None  # show this on the OLED while waiting
    expires_in: int | None = None
    poll_interval: int = 3
    device_id: uuid.UUID | None = None
    device_token: str | None = None  # only once paired, only to the announcer holding the secret
    device_name: str | None = None


class NearbyDeviceOut(BaseModel):
    session_id: uuid.UUID
    hardware_id: str
    display_name: str
    suggested_name: str
    firmware_version: str | None
    local_ip: str | None
    hardware_info: dict
    last_seen_at: datetime
    already_yours: bool


class ClaimIn(BaseModel):
    pairing_code: str = Field(pattern=r"^\d{6}$")
    name: str = Field(default="Kitchen dispenser", min_length=2, max_length=80)


class ClaimOut(BaseModel):
    device: DeviceOut
    reconnected: bool
    message: str
