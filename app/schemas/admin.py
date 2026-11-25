from typing import Literal

from pydantic import BaseModel, Field


class AdminUser(BaseModel):
    id: int
    username: str
    display_name: str | None
    role: Literal["user", "admin"]
    is_active: bool
    household_count: int


class CreateUserRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=6, max_length=72)
    display_name: str | None = Field(default=None, max_length=120)
    role: Literal["user", "admin"] = "user"


class UpdateUserRequest(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)
    role: Literal["user", "admin"] | None = None
    is_active: bool | None = None


class AssignHouseholdsRequest(BaseModel):
    household_ids: list[int] = Field(min_length=1)


class AssignHouseholdsResponse(BaseModel):
    user_id: int
    owned: list[int]


class ImportResponse(BaseModel):
    import_id: int
    status: Literal["completed", "dry_run"]
    filename: str
    total_rows: int
    inserted_rows: int
    rejected_rows: int
    duplicate_rows: int
    quality_flagged_rows: int


class ImportHistoryItem(BaseModel):
    import_id: int
    filename: str
    status: Literal["running", "completed", "failed", "dry_run"]
    total_rows: int
    inserted_rows: int
    rejected_rows: int
    imported_at: str
