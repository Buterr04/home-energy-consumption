from typing import Annotated

from fastapi import Depends, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.errors import APIError
from app.models import Household, User
from app.security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise APIError(
            401, "AUTH_TOKEN_EXPIRED", "A bearer access token is required."
        )

    payload = decode_access_token(credentials.credentials)
    subject = payload.get("sub")
    try:
        user_id = int(subject)
    except (TypeError, ValueError) as exc:
        raise APIError(
            401, "AUTH_TOKEN_EXPIRED", "The access token subject is invalid."
        ) from exc

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise APIError(401, "AUTH_TOKEN_EXPIRED", "The user is not active.")
    return user


def require_admin(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    if user.role != "admin":
        raise APIError(
            403, "FORBIDDEN_ADMIN", "Administrator privileges are required."
        )
    return user


def accessible_household_ids(db: Session, user: User) -> set[int]:
    if user.role == "admin":
        return set(db.scalars(select(Household.id).order_by(Household.id)).all())
    return set(
        db.scalars(
            select(Household.id).where(Household.owner_user_id == user.id)
        ).all()
    )


def ensure_household_access(
    db: Session, user: User, household_ids: list[int]
) -> list[int]:
    if not household_ids:
        raise APIError(
            422, "VALIDATION_ERROR", "At least one household_id is required."
        )
    accessible = accessible_household_ids(db, user)
    denied = [
        household_id
        for household_id in household_ids
        if household_id not in accessible
    ]
    if denied:
        raise APIError(
            403,
            "FORBIDDEN_HOUSEHOLD",
            "One or more households are not accessible.",
        )
    if len(household_ids) > 5:
        raise APIError(
            400,
            "TOO_MANY_HOUSEHOLDS",
            "At most 5 households can be requested at once.",
        )
    return household_ids


PageParam = Annotated[int, Query(ge=1)]
PageSizeParam = Annotated[int, Query(ge=1, le=100)]
