import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.models.enums import CommandStatus, CommandType, MealType


class DispenseSettings(BaseModel):
    """Dispensing strategy sent with every command. The firmware clamps these to
    its own hard limits, so a bad value here cannot remove device-side safety.
    Defaults are untested starting points: tune them on the real hardware."""
    inflight_g: float = Field(default=8, ge=0, le=100,
                              description="Close this many grams early to allow for food still falling.")
    slowdown_g: float = Field(default=25, ge=0, le=200,
                              description="Switch from continuous flow to short pulses this close to the target.")
    pulse_open_ms: int = Field(default=250, ge=50, le=2000)
    pulse_settle_ms: int = Field(default=700, ge=100, le=5000)
    tolerance_g: float = Field(default=3, ge=0.5, le=50,
                               description="Result counts as complete when within this many grams of the target.")
    max_duration_ms: int = Field(default=45000, ge=5000, le=120000)
    no_flow_timeout_ms: int = Field(default=5000, ge=1000, le=30000,
                                    description="Abort if the weight does not rise for this long while open.")
    stable_tolerance_g: float = Field(default=1.5, ge=0.2, le=20)
    stable_window_ms: int = Field(default=1200, ge=300, le=10000)
    settle_timeout_ms: int = Field(default=6000, ge=1000, le=30000)


class DeviceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)


class DeviceUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=80)


class ContainerFood(BaseModel):
    id: uuid.UUID
    name: str
    calories_per_100g: float


class ContainerOut(BaseModel):
    id: uuid.UUID
    slot_number: int
    servo_channel: int
    label: str
    food: ContainerFood | None
    open_angle: int
    closed_angle: int
    capacity_g: float | None
    estimated_remaining_g: float | None
    is_enabled: bool


class ContainerCreate(BaseModel):
    slot_number: int = Field(ge=1, le=16)
    servo_channel: int = Field(ge=0, le=15, description="0 = first servo pin in firmware (GPIO 13), 1 = GPIO 14.")
    label: str = Field(min_length=1, max_length=60)
    food_item_id: uuid.UUID | None = None
    open_angle: int = Field(ge=0, le=180)
    closed_angle: int = Field(ge=0, le=180)
    capacity_g: float | None = Field(default=None, gt=0, le=20000)
    estimated_remaining_g: float | None = Field(default=None, ge=0, le=20000)
    is_enabled: bool = True

    @model_validator(mode="after")
    def angles_differ(self):
        if self.open_angle == self.closed_angle:
            raise ValueError("Open and closed angles must be different.")
        return self


class ContainerUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=60)
    servo_channel: int | None = Field(default=None, ge=0, le=15)
    food_item_id: uuid.UUID | None = None
    clear_food: bool = False
    open_angle: int | None = Field(default=None, ge=0, le=180)
    closed_angle: int | None = Field(default=None, ge=0, le=180)
    capacity_g: float | None = Field(default=None, gt=0, le=20000)
    estimated_remaining_g: float | None = Field(default=None, ge=0, le=20000)
    is_enabled: bool | None = None


class DeviceOut(BaseModel):
    id: uuid.UUID
    name: str
    hardware_id: str | None = None
    token_hint: str
    is_online: bool
    is_registered: bool
    firmware_version: str | None
    hardware_info: dict
    ip_address: str | None
    wifi_rssi: int | None
    device_state: str | None
    last_weight_g: float | None
    last_heartbeat_at: datetime | None
    registered_at: datetime | None
    emergency_stop_active: bool
    dispense_settings: DispenseSettings
    containers: list[ContainerOut]
    active_command_id: uuid.UUID | None
    created_at: datetime


class DeviceCreatedOut(BaseModel):
    device: DeviceOut
    device_token: str
    note: str


class DeviceEventOut(BaseModel):
    id: uuid.UUID
    event_type: str
    severity: str
    message: str
    data: dict
    created_at: datetime


# ---- Device-facing (ESP32) ---------------------------------------------------

class DeviceRegisterIn(BaseModel):
    firmware_version: str = Field(max_length=40)
    servo_count: int = Field(ge=0, le=16)
    hx711_ready: bool
    oled_ready: bool
    calibrated: bool
    ip_address: str | None = Field(default=None, max_length=45)
    wifi_rssi: int | None = Field(default=None, ge=-127, le=0)
    reset_reason: str | None = Field(default=None, max_length=40)
    interrupted_command_id: uuid.UUID | None = None


class DeviceConfigOut(BaseModel):
    device_id: uuid.UUID
    name: str
    emergency_stop_active: bool
    containers: list[dict]
    dispense_settings: DispenseSettings
    server_time: datetime


class HeartbeatIn(BaseModel):
    state: str = Field(default="idle", max_length=32)
    weight_g: float | None = Field(default=None, ge=-10000, le=100000)
    hx711_ready: bool | None = None
    wifi_rssi: int | None = Field(default=None, ge=-127, le=0)
    ip_address: str | None = Field(default=None, max_length=45)
    uptime_s: int | None = Field(default=None, ge=0)
    free_heap: int | None = Field(default=None, ge=0)
    last_error: str | None = Field(default=None, max_length=120)


class HeartbeatOut(BaseModel):
    server_time: datetime
    emergency_stop_active: bool
    has_pending_command: bool


class DeviceCommandOut(BaseModel):
    command_id: uuid.UUID
    type: CommandType
    target_weight_g: float | None
    servo_channel: int | None
    open_angle: int | None
    closed_angle: int | None
    settings: DispenseSettings
    expires_at: datetime


class AckOut(BaseModel):
    command_id: uuid.UUID
    status: CommandStatus
    already_acknowledged: bool
    abort: bool


class ProgressIn(BaseModel):
    weight_g: float = Field(ge=-10000, le=100000)
    phase: str = Field(default="dispensing", max_length=24)


class ProgressOut(BaseModel):
    abort: bool
    reason: str | None


class ResultIn(BaseModel):
    status: Literal["completed", "failed", "cancelled"]
    start_weight_g: float | None = Field(default=None, ge=-10000, le=100000)
    final_weight_g: float | None = Field(default=None, ge=-10000, le=100000)
    dispensed_weight_g: float | None = Field(default=None, ge=-1000, le=5000)
    duration_ms: int | None = Field(default=None, ge=0, le=600000)
    error_code: str | None = Field(default=None, max_length=48)
    error_message: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def completed_needs_weight(self):
        if self.status == "completed" and self.dispensed_weight_g is None:
            raise ValueError("A completed result must include the measured dispensed weight.")
        return self


class ResultOut(BaseModel):
    command_id: uuid.UUID
    status: CommandStatus
    duplicate: bool
    meal_entry_id: uuid.UUID | None


class EmergencyStopIn(BaseModel):
    reason: str | None = Field(default=None, max_length=200)


# ---- User-facing dispenser ---------------------------------------------------

class CommandCreate(BaseModel):
    device_id: uuid.UUID
    command_type: CommandType = CommandType.dispense
    container_id: uuid.UUID | None = None
    target_weight_g: float | None = Field(default=None, gt=0)
    meal_type: MealType | None = None
    consumed_on: date | None = None
    log_to_meals: bool = True

    @model_validator(mode="after")
    def check_dispense_fields(self):
        if self.command_type == CommandType.dispense:
            if self.container_id is None:
                raise ValueError("Choose a container to dispense from.")
            if self.target_weight_g is None:
                raise ValueError("Enter how many grams to dispense.")
            if self.log_to_meals and self.meal_type is None:
                raise ValueError("Choose which meal to log this food under.")
        return self


class CommandLogOut(BaseModel):
    event: str
    status: str
    weight_g: float | None
    message: str | None
    created_at: datetime


class CommandOut(BaseModel):
    id: uuid.UUID
    device_id: uuid.UUID
    container_id: uuid.UUID | None
    container_label: str | None
    food_item_id: uuid.UUID | None
    food_name: str | None
    command_type: CommandType
    status: CommandStatus
    target_weight_g: float | None
    dispensed_weight_g: float | None
    start_weight_g: float | None
    final_weight_g: float | None
    last_progress_weight_g: float | None
    meal_type: MealType | None
    consumed_on: date | None
    log_to_meals: bool
    cancel_requested: bool
    error_code: str | None
    error_message: str | None
    duration_ms: int | None
    meal_entry_id: uuid.UUID | None
    created_at: datetime
    acknowledged_at: datetime | None
    completed_at: datetime | None
    expires_at: datetime
    logs: list[CommandLogOut] = []
