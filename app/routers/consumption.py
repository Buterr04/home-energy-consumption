from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import accessible_household_ids, ensure_household_access, get_current_user
from app.errors import APIError
from app.models import Household, User
from app.schemas.consumption import (
    AverageMeta,
    AveragePoint,
    AverageResponse,
    BreakdownItem,
    BreakdownResponse,
    ConsumptionSeriesItem,
    ConsumptionSeriesMeta,
    ConsumptionSeriesResponse,
)
from app.services.consumption import (
    average_data,
    breakdown_data,
    resolve_date_range,
    series_data,
)

router = APIRouter(prefix="/consumption", tags=["Consumption"])


def _normalize_ids(household_ids: list[int]) -> list[int]:
    ids = list(dict.fromkeys(household_ids))
    if len(ids) > 5:
        raise APIError(
            400,
            "TOO_MANY_HOUSEHOLDS",
            "At most 5 households can be compared at once.",
        )
    return ids


def _validate_appliance_filters(
    include_appliance_ids: list[int],
    exclude_appliance_ids: list[int],
) -> None:
    if include_appliance_ids and exclude_appliance_ids:
        raise APIError(
            400,
            "INVALID_APPLIANCE_FILTER",
            "include_appliance_ids and exclude_appliance_ids cannot be combined.",
        )


@router.get("/series", response_model=ConsumptionSeriesResponse)
def consumption_series(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    household_ids: Annotated[list[int], Query(min_length=1)],
    granularity: Literal["day", "month", "year"] = "day",
    start_date: date | None = None,
    end_date: date | None = None,
    include_appliance_ids: Annotated[list[int] | None, Query()] = None,
    exclude_appliance_ids: Annotated[list[int] | None, Query()] = None,
) -> ConsumptionSeriesResponse:
    ids = _normalize_ids(household_ids)
    ensure_household_access(db, user, ids)
    include_ids = include_appliance_ids or []
    exclude_ids = exclude_appliance_ids or []
    _validate_appliance_filters(include_ids, exclude_ids)
    start, end = resolve_date_range(db, start_date, end_date, granularity)
    items = series_data(
        db,
        ids,
        start,
        end,
        granularity,
        include_ids,
        exclude_ids,
    )
    return ConsumptionSeriesResponse(
        granularity=granularity,
        start_date=start.isoformat(),
        end_date=end.isoformat(),
        items=[ConsumptionSeriesItem(**item) for item in items],
        meta=ConsumptionSeriesMeta(
            excluded_appliance_ids=exclude_ids,
        ),
    )


@router.get("/average", response_model=AverageResponse)
def consumption_average(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    granularity: Literal["day", "month", "year"] = "day",
    start_date: date | None = None,
    end_date: date | None = None,
    scope: Literal["all", "accessible"] = "all",
    include_appliance_ids: Annotated[list[int] | None, Query()] = None,
    exclude_appliance_ids: Annotated[list[int] | None, Query()] = None,
) -> AverageResponse:
    include_ids = include_appliance_ids or []
    exclude_ids = exclude_appliance_ids or []
    _validate_appliance_filters(include_ids, exclude_ids)
    if scope == "accessible":
        ids = sorted(accessible_household_ids(db, user))
    else:
        ids = list(db.scalars(select(Household.id).order_by(Household.id)).all())
    start, end = resolve_date_range(db, start_date, end_date, granularity)
    items = average_data(
        db,
        ids,
        start,
        end,
        granularity,
        include_ids,
        exclude_ids,
    )
    return AverageResponse(
        granularity=granularity,
        scope=scope,
        items=[AveragePoint(**item) for item in items],
        meta=AverageMeta(
            excluded_appliance_ids=exclude_ids,
        ),
    )


@router.get("/breakdown", response_model=BreakdownResponse)
def consumption_breakdown(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    household_id: Annotated[int, Query()],
    start_date: date | None = None,
    end_date: date | None = None,
) -> BreakdownResponse:
    ensure_household_access(db, user, [household_id])
    start, end = resolve_date_range(db, start_date, end_date, "day")
    data = breakdown_data(db, household_id, start, end)
    return BreakdownResponse(
        household_id=data["household_id"],
        start_date=data["start_date"],
        end_date=data["end_date"],
        total_kwh=data["total_kwh"],
        items=[BreakdownItem(**item) for item in data["items"]],
    )
