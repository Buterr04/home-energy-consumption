import csv
import io
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import ensure_household_access, get_current_user
from app.errors import APIError
from app.models import User
from app.services.consumption import report_rows, resolve_date_range

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/summary")
def summary_report(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    household_ids: Annotated[list[int], Query(min_length=1)],
    granularity: Literal["month", "year"] = "month",
    start_date: date | None = None,
    end_date: date | None = None,
    format_: Annotated[Literal["csv"], Query(alias="format")] = "csv",
    include_appliance_ids: Annotated[list[int] | None, Query()] = None,
    exclude_appliance_ids: Annotated[list[int] | None, Query()] = None,
) -> Response:
    ids = list(dict.fromkeys(household_ids))
    if len(ids) > 5:
        raise APIError(
            400,
            "TOO_MANY_HOUSEHOLDS",
            "At most 5 households can be exported at once.",
        )
    ensure_household_access(db, user, ids)
    include_ids = include_appliance_ids or []
    exclude_ids = exclude_appliance_ids or []
    if include_ids and exclude_ids:
        raise APIError(
            400,
            "INVALID_APPLIANCE_FILTER",
            "include_appliance_ids and exclude_appliance_ids cannot be combined.",
        )
    if format_ != "csv":
        raise APIError(
            422, "VALIDATION_ERROR", "Only the csv format is supported."
        )

    start, end = resolve_date_range(db, start_date, end_date, granularity)
    rows = report_rows(
        db,
        ids,
        start,
        end,
        granularity,
        include_ids,
        exclude_ids,
    )

    stream = io.StringIO()
    writer = csv.DictWriter(
        stream,
        fieldnames=[
            "household_id",
            "period",
            "total_kwh",
            "household_size_median",
            "kwh_per_resident",
        ],
    )
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                key: "" if value is None else value for key, value in row.items()
            }
        )
    filename = (
        f"consumption_report_{start.strftime('%Y-%m')}_"
        f"{end.strftime('%Y-%m')}.csv"
    )
    return Response(
        content=stream.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )
