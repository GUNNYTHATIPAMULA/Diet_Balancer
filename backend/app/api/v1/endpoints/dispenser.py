import uuid
from typing import Annotated

from fastapi import APIRouter, Header, Query, status
from pydantic import BaseModel

from app.api.deps import CurrentUser, DbSession
from app.models.enums import MealType
from app.schemas.device import CommandCreate, CommandOut
from app.services import dispenser_service

router = APIRouter(prefix="/dispenser", tags=["dispenser"])


class LogMeasuredIn(BaseModel):
    meal_type: MealType | None = None


@router.post("/commands", response_model=CommandOut, status_code=status.HTTP_201_CREATED)
def create_command(data: CommandCreate, user: CurrentUser, db: DbSession,
                   idempotency_key: Annotated[str | None, Header()] = None):
    """Send the Idempotency-Key header (a UUID per button press) so retries never create a second request."""
    return dispenser_service.create_command(db, user, data, idempotency_key)


@router.get("/commands", response_model=list[CommandOut])
def list_commands(user: CurrentUser, db: DbSession, device_id: uuid.UUID | None = None,
                  limit: int = Query(20, ge=1, le=100)):
    return dispenser_service.list_commands(db, user, device_id, limit)


@router.get("/commands/{command_id}", response_model=CommandOut)
def get_command(command_id: uuid.UUID, user: CurrentUser, db: DbSession):
    return dispenser_service.get_command(db, user, command_id)


@router.post("/commands/{command_id}/cancel", response_model=CommandOut)
def cancel_command(command_id: uuid.UUID, user: CurrentUser, db: DbSession):
    return dispenser_service.cancel_command(db, user, command_id)


@router.post("/commands/{command_id}/log-measured", response_model=CommandOut)
def log_measured(command_id: uuid.UUID, data: LogMeasuredIn, user: CurrentUser, db: DbSession):
    return dispenser_service.log_measured(db, user, command_id, data.meal_type)
