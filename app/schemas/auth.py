from typing import Literal

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=72)


class AuthUser(BaseModel):
    id: int
    username: str
    display_name: str | None
    role: Literal["user", "admin"]


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: AuthUser


class CurrentUser(BaseModel):
    id: int
    username: str
    display_name: str | None
    role: Literal["user", "admin"]
    is_active: bool


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=72)
    new_password: str = Field(min_length=6, max_length=72)
