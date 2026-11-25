from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import (
    PageParam,
    PageSizeParam,
    accessible_household_ids,
    get_current_user,
)
from app.errors import APIError
from app.models import Appliance, EnergyReading, Household, User
from app.schemas.common import Page
from app.schemas.household import (
    HouseholdAppliance,
    HouseholdDetail,
    HouseholdSummary,
)
from app.services.consumption import household_summaries

router = APIRouter(prefix="/households", tags=["Households"])


def _public_summary(summary: dict) -> dict:
    return {
        key: value
        for key, value in summary.items()
        if key != "owner_user_id"
    }


@router.get(
    "",
    response_model=Page[HouseholdSummary],
    response_model_exclude_none=True,
)
def list_households(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    search: Annotated[str | None, Query(max_length=100)] = None,
    page: PageParam = 1,
    page_size: PageSizeParam = 20,
) -> Page[HouseholdSummary]:
    accessible = accessible_household_ids(db, user)
    stmt = select(Household.id).where(Household.id.in_(accessible))
    if search:
        search = search.strip()
        conditions = [Household.display_name.ilike(f"%{search}%")]
        if search.isdigit():
            conditions.append(Household.id == int(search))
        stmt = stmt.where(or_(*conditions))

    total = int(
        db.scalar(
            select(func.count()).select_from(stmt.subquery())
        )
        or 0
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
            HouseholdSummary(
                **_public_summary(summaries[household_id])
            )
            for household_id in ids
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{household_id}",
    response_model=HouseholdDetail,
    response_model_exclude_none=True,
)
def get_household(
    household_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> HouseholdDetail:
    household = db.get(Household, household_id)
    if household is None:
        raise APIError(
            404, "HOUSEHOLD_NOT_FOUND", "The household does not exist."
        )
    if user.role != "admin" and household.owner_user_id != user.id:
        raise APIError(
            403,
            "FORBIDDEN_HOUSEHOLD",
            "One or more households are not accessible.",
        )

    summary = household_summaries(db, [household_id])[household_id]
    appliances = [
        HouseholdAppliance(
            appliance_id=int(row.appliance_id),
            appliance_name=row.appliance_name,
            reading_count=int(row.reading_count),
        )
        for row in db.execute(
            select(
                Appliance.id.label("appliance_id"),
                Appliance.name.label("appliance_name"),
                func.count(EnergyReading.id).label("reading_count"),
            )
            .join(EnergyReading, EnergyReading.appliance_id == Appliance.id)
            .where(EnergyReading.household_id == household_id)
            .group_by(Appliance.id, Appliance.name)
            .order_by(Appliance.name)
        ).all()
    ]
    return HouseholdDetail(
        **_public_summary(summary), appliances=appliances
    )
