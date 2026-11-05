import uuid
from typing import Annotated

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.errors import UnauthorizedError
from app.db.session import get_db
from app.models.device import Device
from app.models.user import User
from app.services import auth_service, device_service

bearer = HTTPBearer(auto_error=False)

DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(db: DbSession,
                     credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise UnauthorizedError("Log in to continue.", code="not_authenticated")
    return auth_service.user_from_token(db, credentials.credentials)


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_header_device(db: DbSession,
                      x_device_id: Annotated[uuid.UUID | None, Header()] = None,
                      x_device_token: Annotated[str | None, Header()] = None) -> Device:
    """Device identified by X-Device-Id + X-Device-Token headers."""
    return device_service.authenticate_device(db, x_device_id, x_device_token)


def get_path_device(device_id: uuid.UUID, db: DbSession,
                    x_device_token: Annotated[str | None, Header()] = None) -> Device:
    """Device identified by the {device_id} path segment + X-Device-Token header."""
    return device_service.authenticate_device(db, device_id, x_device_token)


HeaderDevice = Annotated[Device, Depends(get_header_device)]
PathDevice = Annotated[Device, Depends(get_path_device)]


def get_user_or_device(request: Request, device_id: uuid.UUID, db: DbSession,
                       credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
                       x_device_token: Annotated[str | None, Header()] = None) -> User | Device:
    """Emergency stop may be triggered by the owner (JWT) or by the device itself."""
    if credentials is not None:
        return auth_service.user_from_token(db, credentials.credentials)
    if x_device_token:
        return device_service.authenticate_device(db, device_id, x_device_token)
    raise UnauthorizedError("Log in to continue.", code="not_authenticated")
