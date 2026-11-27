from collections import Counter, defaultdict
from datetime import date, timedelta
from statistics import median
from typing import Literal

from sqlalchemy import delete, func, insert, select
from sqlalchemy.orm import Session

from app.errors import APIError
from app.models import (
    Appliance,
    EnergyReading,
    Household,
    HouseholdProfile,
)

Granularity = Literal["day", "month", "year"]
VALID_GRANULARITIES = {"day", "month", "year"}


def _shift_month(value: date, delta: int) -> date:
    month_index = value.year * 12 + (value.month - 1) + delta
    return date(month_index // 12, month_index % 12 + 1, 1)


def resolve_date_range(
    db: Session,
    start_date: date | None,
    end_date: date | None,
    granularity: Granularity,
) -> tuple[date, date]:
    latest_text = db.scalar(select(func.max(EnergyReading.reading_date)))
    latest = date.fromisoformat(latest_text) if latest_text else date.today()

    if end_date is None:
        end_date = latest
    if start_date is None:
        if granularity == "day":
            start_date = end_date - timedelta(days=29)
        elif granularity == "month":
            start_date = _shift_month(date(end_date.year, end_date.month, 1), -11)
        else:
            start_date = date(end_date.year - 4, 1, 1)

    if start_date > end_date:
        raise APIError(
            400,
            "INVALID_DATE_RANGE",
            "start_date must be earlier than or equal to end_date.",
        )
    return start_date, end_date


def _period_expression(granularity: Granularity):
    if granularity == "day":
        return EnergyReading.reading_date
    if granularity == "month":
        return func.substr(EnergyReading.reading_date, 1, 7)
    return func.substr(EnergyReading.reading_date, 1, 4)


def _dedupe(values: list[int]) -> list[int]:
    return list(dict.fromkeys(values))


def series_data(
    db: Session,
    household_ids: list[int],
    start_date: date,
    end_date: date,
    granularity: Granularity,
    include_appliance_ids: list[int] | None = None,
    exclude_appliance_ids: list[int] | None = None,
) -> list[dict]:
    ids = _dedupe(household_ids)
    if not ids:
        return []

    period_expr = _period_expression(granularity)
    stmt = (
        select(
            EnergyReading.household_id.label("household_id"),
            period_expr.label("period"),
            func.sum(EnergyReading.energy_kwh).label("kwh"),
            func.count(EnergyReading.id).label("reading_count"),
        )
        .where(
            EnergyReading.household_id.in_(ids),
            EnergyReading.reading_date >= start_date.isoformat(),
            EnergyReading.reading_date <= end_date.isoformat(),
        )
        .group_by(EnergyReading.household_id, period_expr)
        .order_by(period_expr, EnergyReading.household_id)
    )
    if include_appliance_ids:
        stmt = stmt.where(
            EnergyReading.appliance_id.in_(_dedupe(include_appliance_ids))
        )
    elif exclude_appliance_ids:
        stmt = stmt.where(
            EnergyReading.appliance_id.not_in(_dedupe(exclude_appliance_ids))
        )

    names = dict(
        db.execute(
            select(Household.id, Household.display_name).where(
                Household.id.in_(ids)
            )
        ).all()
    )
    color_index = {household_id: index for index, household_id in enumerate(ids)}

    rows = db.execute(stmt).all()
    return [
        {
            "household_id": row.household_id,
            "display_name": names.get(row.household_id)
            or f"Home {row.household_id}",
            "period": str(row.period),
            "kwh": round(float(row.kwh or 0), 3),
            "reading_count": int(row.reading_count),
            "color_index": color_index.get(row.household_id, 0),
        }
        for row in rows
    ]


def average_data(
    db: Session,
    household_ids: list[int],
    start_date: date,
    end_date: date,
    granularity: Granularity,
    include_appliance_ids: list[int] | None = None,
    exclude_appliance_ids: list[int] | None = None,
) -> list[dict]:
    ids = _dedupe(household_ids)
    period_expr = _period_expression(granularity)
    expected = len(ids)
    if not ids:
        return []

    home_daily = (
        select(
            EnergyReading.household_id.label("household_id"),
            period_expr.label("period"),
            func.sum(EnergyReading.energy_kwh).label("kwh"),
        )
        .where(
            EnergyReading.household_id.in_(ids),
            EnergyReading.reading_date >= start_date.isoformat(),
            EnergyReading.reading_date <= end_date.isoformat(),
        )
        .group_by(EnergyReading.household_id, period_expr)
        .subquery()
    )
    if include_appliance_ids:
        home_daily = (
            select(
                EnergyReading.household_id.label("household_id"),
                period_expr.label("period"),
                func.sum(EnergyReading.energy_kwh).label("kwh"),
            )
            .where(
                EnergyReading.household_id.in_(ids),
                EnergyReading.reading_date >= start_date.isoformat(),
                EnergyReading.reading_date <= end_date.isoformat(),
                EnergyReading.appliance_id.in_(
                    _dedupe(include_appliance_ids)
                ),
            )
            .group_by(EnergyReading.household_id, period_expr)
            .subquery()
        )
    elif exclude_appliance_ids:
        home_daily = (
            select(
                EnergyReading.household_id.label("household_id"),
                period_expr.label("period"),
                func.sum(EnergyReading.energy_kwh).label("kwh"),
            )
            .where(
                EnergyReading.household_id.in_(ids),
                EnergyReading.reading_date >= start_date.isoformat(),
                EnergyReading.reading_date <= end_date.isoformat(),
                EnergyReading.appliance_id.not_in(
                    _dedupe(exclude_appliance_ids)
                ),
            )
            .group_by(EnergyReading.household_id, period_expr)
            .subquery()
        )

    aggregate = (
        select(
            home_daily.c.period.label("period"),
            func.avg(home_daily.c.kwh).label("avg_kwh"),
            func.count(home_daily.c.household_id).label("household_count"),
        )
        .group_by(home_daily.c.period)
        .order_by(home_daily.c.period)
    )
    rows = db.execute(aggregate).all()
    return [
        {
            "period": str(row.period),
            "avg_kwh": round(float(row.avg_kwh or 0), 3),
            "household_count": int(row.household_count),
            "expected_households": expected,
        }
        for row in rows
    ]


def breakdown_data(
    db: Session,
    household_id: int,
    start_date: date,
    end_date: date,
) -> dict:
    rows = db.execute(
        select(
            Appliance.id.label("appliance_id"),
            Appliance.name.label("appliance_name"),
            func.sum(EnergyReading.energy_kwh).label("kwh"),
        )
        .join(Appliance, Appliance.id == EnergyReading.appliance_id)
        .where(
            EnergyReading.household_id == household_id,
            EnergyReading.reading_date >= start_date.isoformat(),
            EnergyReading.reading_date <= end_date.isoformat(),
        )
        .group_by(Appliance.id, Appliance.name)
        .order_by(func.sum(EnergyReading.energy_kwh).desc())
    ).all()

    total = round(sum(float(row.kwh or 0) for row in rows), 3)
    items = [
        {
            "appliance_id": int(row.appliance_id),
            "appliance_name": row.appliance_name,
            "kwh": round(float(row.kwh or 0), 3),
            "share": round(float(row.kwh or 0) / total, 3) if total else 0.0,
        }
        for row in rows
    ]
    return {
        "household_id": household_id,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "total_kwh": total,
        "items": items,
    }


def household_monthly_totals(
    db: Session,
    household_id: int,
    start_date: date,
    end_date: date,
) -> list[dict]:
    aggregate_ids = set(
        db.scalars(
            select(Appliance.id).where(
                func.lower(Appliance.name) == "aggregate"
            )
        )
    )
    rows = db.execute(
        select(
            EnergyReading.reading_date.label("reading_date"),
            EnergyReading.appliance_id.label("appliance_id"),
            func.sum(EnergyReading.energy_kwh).label("kwh"),
            func.avg(EnergyReading.outdoor_temp_c).label("temp_c"),
            func.avg(EnergyReading.household_size).label("household_size"),
        )
        .where(
            EnergyReading.household_id == household_id,
            EnergyReading.reading_date >= start_date.isoformat(),
            EnergyReading.reading_date <= end_date.isoformat(),
        )
        .group_by(EnergyReading.reading_date, EnergyReading.appliance_id)
    ).all()

    daily: dict[str, dict] = {}
    for row in rows:
        item = daily.setdefault(
            str(row.reading_date),
            {
                "aggregate_kwh": 0.0,
                "component_kwh": 0.0,
                "has_aggregate": False,
                "has_components": False,
                "temp_values": [],
                "size_values": [],
            },
        )
        if int(row.appliance_id) in aggregate_ids:
            item["aggregate_kwh"] += float(row.kwh or 0)
            item["has_aggregate"] = True
        else:
            item["component_kwh"] += float(row.kwh or 0)
            item["has_components"] = True
        if row.temp_c is not None:
            item["temp_values"].append(float(row.temp_c))
        if row.household_size is not None:
            item["size_values"].append(float(row.household_size))

    monthly: dict[str, dict] = {}
    for reading_date, item in daily.items():
        period = reading_date[:7]
        month = monthly.setdefault(
            period,
            {
                "total_kwh": 0.0,
                "reading_days": 0,
                "temp_values": [],
                "bases": set(),
            },
        )
        total_kwh = (
            item["aggregate_kwh"]
            if item["has_aggregate"]
            else item["component_kwh"]
        )
        month["total_kwh"] += total_kwh
        month["reading_days"] += 1
        month["temp_values"].extend(item["temp_values"])
        month["bases"].add(
            "aggregate" if item["has_aggregate"] else "appliance_sum"
        )

    result = []
    for period, month in sorted(monthly.items()):
        days = int(month["reading_days"])
        temps = month["temp_values"]
        bases = month["bases"]
        result.append(
            {
                "period": period,
                "total_kwh": round(float(month["total_kwh"]), 3),
                "actual_avg_daily_kwh": round(
                    float(month["total_kwh"]) / days, 3
                ),
                "temperature_c": (
                    round(sum(temps) / len(temps), 2) if temps else None
                ),
                "reading_days": days,
                "basis": (
                    next(iter(bases)) if len(bases) == 1 else "mixed"
                ),
            }
        )
    return result


def household_monthly_temp_profile(
    db: Session, household_id: int
) -> dict[int, float]:
    rows = db.execute(
        select(
            func.substr(EnergyReading.reading_date, 6, 2).label("month"),
            func.avg(EnergyReading.outdoor_temp_c).label("temp_c"),
        )
        .where(EnergyReading.household_id == household_id)
        .group_by(func.substr(EnergyReading.reading_date, 6, 2))
    ).all()
    return {
        int(row.month): round(float(row.temp_c), 2)
        for row in rows
        if row.month is not None and row.temp_c is not None
    }


def _household_stats(
    db: Session, household_ids: list[int] | None = None
) -> dict[int, dict]:
    ids_stmt = select(Household.id)
    if household_ids is not None:
        if not household_ids:
            return {}
        ids_stmt = ids_stmt.where(Household.id.in_(household_ids))
    ids = list(db.scalars(ids_stmt.order_by(Household.id)).all())
    if not ids:
        return {}

    stats = db.execute(
        select(
            EnergyReading.household_id.label("household_id"),
            func.count(EnergyReading.id).label("reading_count"),
            func.count(func.distinct(EnergyReading.reading_date)).label(
                "day_count"
            ),
            func.sum(EnergyReading.energy_kwh).label("total_kwh"),
            func.avg(EnergyReading.outdoor_temp_c).label("avg_temp_c"),
            func.min(EnergyReading.reading_date).label("first_date"),
            func.max(EnergyReading.reading_date).label("last_date"),
        )
        .where(EnergyReading.household_id.in_(ids))
        .group_by(EnergyReading.household_id)
    ).all()
    raw = {int(row.household_id): row for row in stats}

    sizes: dict[int, list[int]] = defaultdict(list)
    for household_id, size in db.execute(
        select(EnergyReading.household_id, EnergyReading.household_size)
        .where(EnergyReading.household_id.in_(ids))
        .order_by(EnergyReading.household_id, EnergyReading.household_size)
    ):
        sizes[int(household_id)].append(int(size))

    result: dict[int, dict] = {}
    for household_id in ids:
        row = raw.get(household_id)
        size_values = sizes.get(household_id, [])
        size_median = float(median(size_values)) if size_values else None
        size_mode = Counter(size_values).most_common(1)[0][0] if size_values else None
        avg_daily = (
            float(row.total_kwh or 0) / int(row.day_count)
            if row is not None and row.day_count
            else None
        )
        result[household_id] = {
            "size_median": round(size_median, 2) if size_median is not None else None,
            "size_mode": size_mode,
            "avg_temp_c": round(float(row.avg_temp_c), 2)
            if row is not None and row.avg_temp_c is not None
            else None,
            "avg_daily_kwh": round(avg_daily, 3) if avg_daily is not None else None,
            "reading_count": int(row.reading_count) if row is not None else 0,
            "first_date": (
                str(row.first_date)
                if row is not None and row.first_date
                else None
            ),
            "last_date": (
                str(row.last_date)
                if row is not None and row.last_date
                else None
            ),
        }
    return result


def household_summaries(
    db: Session, household_ids: list[int] | None = None
) -> dict[int, dict]:
    rows = db.execute(
        select(Household.id, Household.display_name, Household.owner_user_id)
        .order_by(Household.id)
    ).all()
    requested = set(household_ids) if household_ids is not None else None
    household_rows = [
        row for row in rows if requested is None or row.id in requested
    ]
    stats = _household_stats(db, [row.id for row in household_rows])

    return {
        int(row.id): {
            "household_id": int(row.id),
            "display_name": row.display_name or f"Home {row.id}",
            "size_median": stats.get(row.id, {}).get("size_median"),
            "avg_temp_c": stats.get(row.id, {}).get("avg_temp_c"),
            "avg_daily_kwh": stats.get(row.id, {}).get("avg_daily_kwh"),
            "reading_count": stats.get(row.id, {}).get("reading_count", 0),
            "first_date": stats.get(row.id, {}).get("first_date"),
            "last_date": stats.get(row.id, {}).get("last_date"),
            "owner_user_id": row.owner_user_id,
        }
        for row in household_rows
    }


def refresh_household_profiles(
    db: Session, household_ids: list[int] | None = None
) -> None:
    stats = _household_stats(db, household_ids)
    ids = list(stats)
    if not ids:
        return

    db.execute(
        delete(HouseholdProfile).where(HouseholdProfile.household_id.in_(ids))
    )
    db.execute(
        insert(HouseholdProfile),
        [
            {
                "household_id": household_id,
                "size_median": value["size_median"],
                "size_mode": value["size_mode"],
                "avg_temp_c": value["avg_temp_c"],
                "avg_daily_kwh": value["avg_daily_kwh"],
                "reading_count": value["reading_count"],
                "first_date": value["first_date"],
                "last_date": value["last_date"],
            }
            for household_id, value in stats.items()
        ],
    )


def report_rows(
    db: Session,
    household_ids: list[int],
    start_date: date,
    end_date: date,
    granularity: Literal["month", "year"],
    include_appliance_ids: list[int] | None = None,
    exclude_appliance_ids: list[int] | None = None,
) -> list[dict]:
    series = series_data(
        db,
        household_ids,
        start_date,
        end_date,
        granularity,
        include_appliance_ids,
        exclude_appliance_ids,
    )

    period_expr = _period_expression(granularity)
    size_stmt = (
        select(
            EnergyReading.household_id.label("household_id"),
            period_expr.label("period"),
            EnergyReading.household_size.label("household_size"),
        )
        .where(
            EnergyReading.household_id.in_(_dedupe(household_ids)),
            EnergyReading.reading_date >= start_date.isoformat(),
            EnergyReading.reading_date <= end_date.isoformat(),
        )
    )
    if include_appliance_ids:
        size_stmt = size_stmt.where(
            EnergyReading.appliance_id.in_(_dedupe(include_appliance_ids))
        )
    elif exclude_appliance_ids:
        size_stmt = size_stmt.where(
            EnergyReading.appliance_id.not_in(_dedupe(exclude_appliance_ids))
        )

    sizes: dict[tuple[int, str], list[int]] = defaultdict(list)
    for row in db.execute(size_stmt).all():
        sizes[(int(row.household_id), str(row.period))].append(
            int(row.household_size)
        )

    result = []
    for item in series:
        key = (item["household_id"], item["period"])
        size_values = sizes.get(key, [])
        size_median = float(median(size_values)) if size_values else None
        if size_median is not None and size_median.is_integer():
            size_median = int(size_median)
        per_resident = (
            round(item["kwh"] / size_median, 2)
            if size_median not in (None, 0)
            else None
        )
        result.append(
            {
                "household_id": item["household_id"],
                "period": item["period"],
                "total_kwh": item["kwh"],
                "household_size_median": size_median,
                "kwh_per_resident": per_resident,
            }
        )
    return result


def household_avg_daily_kwh(db: Session, household_id: int) -> float | None:
    profile = db.get(HouseholdProfile, household_id)
    if profile is not None and profile.avg_daily_kwh is not None:
        return float(profile.avg_daily_kwh)

    row = db.execute(
        select(
            func.sum(EnergyReading.energy_kwh).label("total"),
            func.count(func.distinct(EnergyReading.reading_date)).label("days"),
        ).where(EnergyReading.household_id == household_id)
    ).one()
    if not row.days:
        return None
    return float(row.total or 0) / int(row.days)
