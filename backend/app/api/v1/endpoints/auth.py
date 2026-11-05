from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUser, DbSession
from app.core.rate_limit import rate_limit
from app.schemas.auth import (ChangePasswordRequest, LoginRequest, RegisterRequest, TokenResponse, UpdateMeRequest,
                              UserOut)
from app.schemas.common import MessageOut
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(rate_limit("register", 10, 3600))])
def register(data: RegisterRequest, db: DbSession):
    return auth_service.register(db, data)


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(rate_limit("login", 10, 60))])
def login(data: LoginRequest, db: DbSession):
    return auth_service.login(db, data)


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser, db: DbSession):
    return auth_service.to_user_out(db, user)


@router.patch("/me", response_model=UserOut)
def update_me(data: UpdateMeRequest, user: CurrentUser, db: DbSession):
    return auth_service.update_me(db, user, data)


@router.post("/change-password", response_model=TokenResponse,
             dependencies=[Depends(rate_limit("change_password", 5, 300))])
def change_password(data: ChangePasswordRequest, user: CurrentUser, db: DbSession):
    return auth_service.change_password(db, user, data)


@router.post("/logout", response_model=MessageOut)
def logout(user: CurrentUser):
    # Access tokens are stateless; the client discards its token.
    return MessageOut(message="Logged out.")


@router.post("/logout-all", response_model=MessageOut)
def logout_all(user: CurrentUser, db: DbSession):
    auth_service.logout_everywhere(db, user)
    return MessageOut(message="Signed out of all sessions.")
