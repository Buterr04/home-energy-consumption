from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.config import get_settings
from app.errors import APIError


def hash_password(password: str) -> str:
    if len(password.encode("utf-8")) > 72:
        raise APIError(
            422,
            "VALIDATION_ERROR",
            "Password must be at most 72 bytes when UTF-8 encoded.",
        )
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"), password_hash.encode("utf-8")
        )
    except ValueError:
        return False


def create_access_token(user_id: int, role: str) -> tuple[str, int]:
    settings = get_settings()
    expires_delta = timedelta(minutes=settings.access_token_expire_minutes)
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
    }
    token = jwt.encode(
        payload, settings.jwt_secret, algorithm=settings.jwt_algorithm
    )
    return token, int(expires_delta.total_seconds())


def decode_access_token(token: str) -> dict:
    settings = get_settings()
    try:
        return jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.ExpiredSignatureError as exc:
        raise APIError(
            401, "AUTH_TOKEN_EXPIRED", "The access token has expired."
        ) from exc
    except jwt.PyJWTError as exc:
        raise APIError(
            401, "AUTH_TOKEN_EXPIRED", "The access token is invalid."
        ) from exc
