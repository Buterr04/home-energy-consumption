from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.errors import APIError
from app.models import User
from app.schemas.auth import (
    AuthUser,
    ChangePasswordRequest,
    CurrentUser,
    LoginRequest,
    LoginResponse,
)
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    db: Annotated[Session, Depends(get_db)],
) -> LoginResponse:
    user = db.scalar(select(User).where(User.username == payload.username))
    if (
        user is None
        or not user.is_active
        or not verify_password(payload.password, user.password_hash)
    ):
        raise APIError(
            401,
            "AUTH_INVALID_CREDENTIALS",
            "The username or password is incorrect.",
        )

    token, expires_in = create_access_token(user.id, user.role)
    return LoginResponse(
        access_token=token,
        expires_in=expires_in,
        user=AuthUser(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            role=user.role,
        ),
    )


@router.get("/me", response_model=CurrentUser)
def current_user(
    user: Annotated[User, Depends(get_current_user)],
) -> CurrentUser:
    return CurrentUser(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
        is_active=user.is_active,
    )


@router.post("/change-password", status_code=204)
def change_password(
    payload: ChangePasswordRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    if not verify_password(payload.current_password, user.password_hash):
        raise APIError(
            400, "INVALID_CURRENT_PASSWORD", "The current password is incorrect."
        )
    user.password_hash = hash_password(payload.new_password)
    db.commit()
    return Response(status_code=204)
