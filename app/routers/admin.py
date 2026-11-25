from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy import String as SQLString
from sqlalchemy import cast, func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import PageParam, PageSizeParam, require_admin
from app.errors import APIError
from app.models import Household, ImportBatch, User
from app.schemas.admin import (
    AdminUser,
    AssignHouseholdsRequest,
    AssignHouseholdsResponse,
    CreateUserRequest,
    ImportHistoryItem,
    ImportResponse,
    UpdateUserRequest,
)
from app.schemas.common import Page
from app.schemas.household import HouseholdSummary
from app.security import hash_password
from app.services.consumption import household_summaries
from app.services.imports import import_csv

router = APIRouter(prefix="/admin", tags=["Administration"])


def _user_response(db: Session, user: User) -> AdminUser:
    household_count = int(
        db.scalar(
            select(func.count(Household.id)).where(
                Household.owner_user_id == user.id
            )
        )
        or 0
    )
    return AdminUser(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
        is_active=user.is_active,
        household_count=household_count,
    )


@router.get("/users", response_model=Page[AdminUser])
def list_users(
    _admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
    page: PageParam = 1,
    page_size: PageSizeParam = 20,
) -> Page[AdminUser]:
    total = int(db.scalar(select(func.count(User.id))) or 0)
    users = list(
        db.scalars(
            select(User)
            .order_by(User.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return Page[AdminUser](
        items=[_user_response(db, user) for user in users],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/users", response_model=AdminUser, status_code=201)
def create_user(
    payload: CreateUserRequest,
    _admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> AdminUser:
    if db.scalar(select(User).where(User.username == payload.username)):
        raise APIError(
            409, "USERNAME_EXISTS", "The username is already registered."
        )
    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
        role=payload.role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _user_response(db, user)


@router.patch("/users/{user_id}", response_model=AdminUser)
def update_user(
    user_id: int,
    payload: UpdateUserRequest,
    _admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> AdminUser:
    user = db.get(User, user_id)
    if user is None:
        raise APIError(404, "USER_NOT_FOUND", "The user does not exist.")
    if payload.display_name is not None:
        user.display_name = payload.display_name
    if payload.role is not None:
        user.role = payload.role
    if payload.is_active is not None:
        user.is_active = payload.is_active
    db.commit()
    return _user_response(db, user)


@router.post(
    "/users/{user_id}/households",
    response_model=AssignHouseholdsResponse,
)
def assign_households(
    user_id: int,
    payload: AssignHouseholdsRequest,
    _admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> AssignHouseholdsResponse:
    user = db.get(User, user_id)
    if user is None:
        raise APIError(404, "USER_NOT_FOUND", "The user does not exist.")
    ids = list(dict.fromkeys(payload.household_ids))
    existing = set(
        db.scalars(select(Household.id).where(Household.id.in_(ids))).all()
    )
    missing = [
        household_id for household_id in ids if household_id not in existing
    ]
    if missing:
        raise APIError(
            404,
            "HOUSEHOLD_NOT_FOUND",
            f"Households do not exist: {missing}.",
        )
    for household in db.scalars(
        select(Household).where(Household.id.in_(ids))
    ).all():
        household.owner_user_id = user.id
    db.commit()
    return AssignHouseholdsResponse(user_id=user_id, owned=sorted(ids))


@router.get("/households", response_model=Page[HouseholdSummary])
def list_all_households(
    _admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
    search: Annotated[str | None, Query(max_length=100)] = None,
    page: PageParam = 1,
    page_size: PageSizeParam = 20,
) -> Page[HouseholdSummary]:
    stmt = select(Household.id)
    if search and search.strip():
        search = search.strip()
        stmt = stmt.where(
            cast(Household.id, SQLString).like(f"%{search}%")
            | Household.display_name.ilike(f"%{search}%")
        )
    total = int(
        db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    )
    ids = list(
        db.scalars(
            stmt.order_by(Household.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    summaries = household_summaries(db, ids)
    return Page[HouseholdSummary](
        items=[
            HouseholdSummary(**summaries[household_id])
            for household_id in ids
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/imports", response_model=ImportResponse)
async def upload_csv(
    _admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
    file: Annotated[UploadFile, File(...)],
    dry_run: Annotated[bool, Form()] = False,
) -> ImportResponse:
    raw_content = await file.read()
    try:
        result = import_csv(
            db,
            filename=file.filename or "upload.csv",
            raw_content=raw_content,
            dry_run=dry_run,
        )
        db.commit()
    except APIError:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise APIError(
            500, "IMPORT_FAILED", "The CSV file could not be imported."
        ) from exc
    return ImportResponse(**result)


@router.get("/imports", response_model=Page[ImportHistoryItem])
def list_imports(
    _admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
    page: PageParam = 1,
    page_size: PageSizeParam = 20,
) -> Page[ImportHistoryItem]:
    total = int(db.scalar(select(func.count(ImportBatch.id))) or 0)
    batches = list(
        db.scalars(
            select(ImportBatch)
            .order_by(ImportBatch.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return Page[ImportHistoryItem](
        items=[
            ImportHistoryItem(
                import_id=batch.id,
                filename=batch.filename,
                status=batch.status,
                total_rows=batch.total_rows,
                inserted_rows=batch.inserted_rows,
                rejected_rows=batch.rejected_rows,
                imported_at=batch.imported_at,
            )
            for batch in batches
        ],
        total=total,
        page=page,
        page_size=page_size,
    )
