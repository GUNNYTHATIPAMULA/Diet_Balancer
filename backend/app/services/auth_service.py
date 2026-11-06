import uuid

import jwt
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, UnauthorizedError
from app.core.security import create_access_token, decode_access_token, hash_password, verify_password
from app.models.user import User
from app.repositories import users as user_repo
from app.schemas.auth import (ChangePasswordRequest, LoginRequest, RegisterRequest, TokenResponse, UpdateMeRequest,
                              UserOut)

# Used to keep login timing similar whether or not the email exists.
_DUMMY_HASH = hash_password("timing-equaliser-password-1")


def to_user_out(db: Session, user: User) -> UserOut:
    return UserOut(id=user.id, email=user.email, full_name=user.full_name, created_at=user.created_at,
                   has_profile=user_repo.get_profile(db, user.id) is not None)


def _token_response(db: Session, user: User) -> TokenResponse:
    token, expires_in = create_access_token(user.id, user.token_version)
    return TokenResponse(access_token=token, expires_in=expires_in, user=to_user_out(db, user))


def register(db: Session, data: RegisterRequest) -> TokenResponse:
    email = data.email.lower()
    if user_repo.get_by_email(db, email):
        raise ConflictError("An account with this email already exists.", code="email_taken")
    user = User(email=email, full_name=data.full_name, password_hash=hash_password(data.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError("An account with this email already exists.", code="email_taken")
    db.refresh(user)
    return _token_response(db, user)


def login(db: Session, data: LoginRequest) -> TokenResponse:
    user = user_repo.get_by_email(db, data.email)
    if user is None:
        verify_password(data.password, _DUMMY_HASH)
        raise UnauthorizedError("Email or password is incorrect.", code="invalid_credentials")
    if not verify_password(data.password, user.password_hash):
        raise UnauthorizedError("Email or password is incorrect.", code="invalid_credentials")
    if not user.is_active:
        raise UnauthorizedError("This account is disabled.", code="account_disabled")
    return _token_response(db, user)


def user_from_token(db: Session, token: str) -> User:
    try:
        payload = decode_access_token(token)
        user_id = uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, ValueError, KeyError):
        raise UnauthorizedError("Your session has expired. Log in again.", code="invalid_token")
    user = user_repo.get_by_id(db, user_id)
    if user is None or not user.is_active or payload.get("ver") != user.token_version:
        raise UnauthorizedError("Your session has expired. Log in again.", code="invalid_token")
    return user


def update_me(db: Session, user: User, data: UpdateMeRequest) -> UserOut:
    user.full_name = " ".join(data.full_name.split())
    db.commit()
    return to_user_out(db, user)


def change_password(db: Session, user: User, data: ChangePasswordRequest) -> TokenResponse:
    if not verify_password(data.current_password, user.password_hash):
        raise UnauthorizedError("Current password is incorrect.", code="invalid_credentials")
    user.password_hash = hash_password(data.new_password)
    user.token_version += 1  # sign out other sessions
    db.commit()
    return _token_response(db, user)


def logout_everywhere(db: Session, user: User) -> None:
    user.token_version += 1
    db.commit()
