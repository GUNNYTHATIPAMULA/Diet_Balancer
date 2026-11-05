import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, SmallInteger,
                        String, Text, UniqueConstraint, Uuid, func, text)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, JSONType, TimestampMixin
from app.models.enums import CommandStatus, CommandType, MealType, db_enum


class Device(Base, TimestampMixin):
    __tablename__ = "devices"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True,
                                                     nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    # Set when the device was connected by pairing (e.g. "DB-3A7F1C", from its MAC address).
    hardware_id: Mapped[str | None] = mapped_column(String(32), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    token_hint: Mapped[str] = mapped_column(String(8), nullable=False)
    firmware_version: Mapped[str | None] = mapped_column(String(40))
    hardware_info: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    wifi_rssi: Mapped[int | None] = mapped_column(SmallInteger)
    device_state: Mapped[str | None] = mapped_column(String(32))
    last_weight_g: Mapped[Decimal | None] = mapped_column(Numeric(7, 1))
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    registered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    emergency_stop_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    dispense_settings: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)

    containers: Mapped[list["DeviceContainer"]] = relationship(
        back_populates="device", cascade="all, delete-orphan", order_by="DeviceContainer.slot_number"
    )


class DeviceContainer(Base, TimestampMixin):
    """Maps a physical container slot to a servo channel and a food.

    servo_channel is an index into the firmware's servo pin list
    (channel 0 = GPIO 13, channel 1 = GPIO 14 in the current prototype)."""
    __tablename__ = "device_containers"
    __table_args__ = (
        UniqueConstraint("device_id", "slot_number", name="uq_device_containers_slot"),
        UniqueConstraint("device_id", "servo_channel", name="uq_device_containers_servo"),
        CheckConstraint("open_angle BETWEEN 0 AND 180 AND closed_angle BETWEEN 0 AND 180", name="angles"),
        CheckConstraint("servo_channel BETWEEN 0 AND 15", name="servo_channel_range"),
        CheckConstraint("capacity_g IS NULL OR capacity_g > 0", name="capacity_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    device_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), nullable=False)
    slot_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    servo_channel: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    label: Mapped[str] = mapped_column(String(60), nullable=False)
    food_item_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("food_items.id", ondelete="SET NULL"))
    open_angle: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    closed_angle: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    capacity_g: Mapped[Decimal | None] = mapped_column(Numeric(7, 1))
    # Software estimate (capacity minus confirmed dispenses). The prototype has a
    # single load cell under the bowl, so container contents are not measured.
    estimated_remaining_g: Mapped[Decimal | None] = mapped_column(Numeric(7, 1))
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    device: Mapped[Device] = relationship(back_populates="containers")
    food: Mapped["FoodItem | None"] = relationship(lazy="joined")  # noqa: F821


class DispensingCommand(Base):
    __tablename__ = "dispensing_commands"
    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_dispensing_commands_idempotency"),
        # At most one in-flight command per device, enforced by the database.
        Index("uq_dispensing_commands_one_active_per_device", "device_id", unique=True,
              postgresql_where=text("status IN ('pending', 'acknowledged', 'dispensing')")),
        Index("ix_dispensing_commands_device_status", "device_id", "status"),
        CheckConstraint("target_weight_g IS NULL OR target_weight_g > 0", name="target_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    device_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    container_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("device_containers.id", ondelete="SET NULL"))
    food_item_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("food_items.id", ondelete="SET NULL"))
    command_type: Mapped[CommandType] = mapped_column(db_enum(CommandType, "command_type"), nullable=False)
    status: Mapped[CommandStatus] = mapped_column(db_enum(CommandStatus, "command_status"), nullable=False,
                                                  default=CommandStatus.pending)
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    target_weight_g: Mapped[Decimal | None] = mapped_column(Numeric(7, 1))
    meal_type: Mapped[MealType | None] = mapped_column(db_enum(MealType, "meal_type"))
    consumed_on: Mapped[date | None] = mapped_column(Date)
    log_to_meals: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Exactly what was sent to the device (servo channel, angles, strategy).
    parameters: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    start_weight_g: Mapped[Decimal | None] = mapped_column(Numeric(7, 1))
    final_weight_g: Mapped[Decimal | None] = mapped_column(Numeric(7, 1))
    dispensed_weight_g: Mapped[Decimal | None] = mapped_column(Numeric(7, 1))
    last_progress_weight_g: Mapped[Decimal | None] = mapped_column(Numeric(7, 1))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(String(48))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    device: Mapped[Device] = relationship()
    container: Mapped[DeviceContainer | None] = relationship()
    food: Mapped["FoodItem | None"] = relationship(lazy="joined")  # noqa: F821
    logs: Mapped[list["DispensingLog"]] = relationship(
        back_populates="command", cascade="all, delete-orphan", order_by="DispensingLog.created_at"
    )


class DispensingLog(Base):
    """Audit trail of one command: every status change and progress report."""
    __tablename__ = "dispensing_logs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    command_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("dispensing_commands.id", ondelete="CASCADE"),
                                                  index=True, nullable=False)
    event: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    weight_g: Mapped[Decimal | None] = mapped_column(Numeric(7, 1))
    message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    command: Mapped[DispensingCommand] = relationship(back_populates="logs")


class DeviceEvent(Base):
    """Device-level audit/event log (registration, errors, emergency stops...)."""
    __tablename__ = "device_events"
    __table_args__ = (Index("ix_device_events_device_created", "device_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    device_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    severity: Mapped[str] = mapped_column(String(10), default="info", nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    data: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PairingSession(Base):
    """A dispenser that is on the network but not yet connected to an account.

    The device announces itself with a random secret (kept on the device). The server
    gives it a 6-digit code to show on its OLED. A signed-in user who types that code
    claims the device; the new device token is then handed only to the announcer that
    knows the secret, and wiped once the device has authenticated with it."""
    __tablename__ = "device_pairing_sessions"
    __table_args__ = (
        Index("uq_pairing_code_waiting", "pairing_code", unique=True, postgresql_where=text("status = 'waiting'")),
        Index("ix_pairing_status_seen", "status", "last_seen_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    hardware_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    secret_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    pairing_code: Mapped[str] = mapped_column(String(6), nullable=False)
    status: Mapped[str] = mapped_column(String(12), default="waiting", nullable=False)  # waiting|claimed|delivered
    public_ip: Mapped[str | None] = mapped_column(String(45))
    local_ip: Mapped[str | None] = mapped_column(String(45))
    firmware_version: Mapped[str | None] = mapped_column(String(40))
    device_name: Mapped[str | None] = mapped_column(String(80))   # name set in the firmware, shown in "nearby"
    hardware_info: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    claimed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    device_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"))
    pending_token: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
