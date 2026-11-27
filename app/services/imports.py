import csv
import io
import math
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from app.errors import APIError
from app.models import Appliance, EnergyReading, Household, ImportBatch
from app.services.consumption import refresh_household_profiles

VALID_SEASONS = {"Winter", "Spring", "Summer", "Fall"}
IMPORT_CHUNK_SIZE = 5000


def seasonal_quality_flag(season: str, temperature: float) -> str:
    """Flag temperatures that are implausible for the labeled season."""
    if season == "Winter" and (temperature < -10 or temperature > 24):
        return "seasonal_temp_outlier"
    if season == "Summer" and (temperature < 2 or temperature > 42):
        return "seasonal_temp_outlier"
    if season in {"Spring", "Fall"} and (
        temperature < -8 or temperature > 38
    ):
        return "seasonal_temp_outlier"
    return "ok"


def _find_header(fieldnames: list[str], prefix: str) -> str | None:
    wanted = prefix.lower()
    for fieldname in fieldnames:
        if fieldname and fieldname.strip().lower().startswith(wanted):
            return fieldname
    return None


def _resolve_headers(fieldnames: list[str]) -> dict[str, str]:
    prefixes = {
        "home_id": "home id",
        "appliance": "appliance type",
        "energy": "energy consumption",
        "time": "time",
        "date": "date",
        "temperature": "outdoor temperature",
        "season": "season",
        "household_size": "household size",
    }
    resolved = {
        key: _find_header(fieldnames, prefix)
        for key, prefix in prefixes.items()
    }
    missing = [key for key, value in resolved.items() if value is None]
    if missing:
        raise APIError(
            500,
            "IMPORT_FAILED",
            f"CSV is missing required columns: {', '.join(missing)}.",
        )
    return {key: value for key, value in resolved.items() if value is not None}


def _parse_row(raw: dict, headers: dict[str, str]) -> dict:
    home_text = (raw.get(headers["home_id"]) or "").strip()
    appliance_name = (raw.get(headers["appliance"]) or "").strip()
    energy_text = (raw.get(headers["energy"]) or "").strip()
    time_text = (raw.get(headers["time"]) or "").strip()
    date_text = (raw.get(headers["date"]) or "").strip()
    temp_text = (raw.get(headers["temperature"]) or "").strip()
    season = (raw.get(headers["season"]) or "").strip()
    size_text = (raw.get(headers["household_size"]) or "").strip()

    if not all(
        [
            home_text,
            appliance_name,
            energy_text,
            time_text,
            date_text,
            temp_text,
            season,
            size_text,
        ]
    ):
        raise ValueError("One or more required fields are empty.")

    home_id = int(home_text)
    if home_id <= 0:
        raise ValueError("Home ID must be a positive integer.")

    energy = float(energy_text)
    temperature = float(temp_text)
    if not math.isfinite(energy) or energy < 0:
        raise ValueError("Energy Consumption must be a finite non-negative number.")
    if not math.isfinite(temperature):
        raise ValueError("Outdoor Temperature must be a finite number.")

    datetime.strptime(date_text, "%Y-%m-%d")
    datetime.strptime(time_text, "%H:%M")

    if season not in VALID_SEASONS:
        raise ValueError("Season must be Winter, Spring, Summer, or Fall.")

    household_size = int(size_text)
    if not 1 <= household_size <= 20:
        raise ValueError("Household Size must be between 1 and 20.")

    return {
        "household_id": home_id,
        "appliance_name": appliance_name,
        "energy_kwh": energy,
        "reading_time": time_text,
        "reading_date": date_text,
        "outdoor_temp_c": temperature,
        "season": season,
        "household_size": household_size,
        "quality_flag": seasonal_quality_flag(season, temperature),
    }


def import_csv(
    db: Session,
    *,
    filename: str,
    raw_content: bytes | str,
    dry_run: bool = False,
) -> dict:
    text = (
        raw_content.decode("latin-1")
        if isinstance(raw_content, bytes)
        else raw_content
    )
    reader = csv.DictReader(io.StringIO(text, newline=""))
    if not reader.fieldnames:
        raise APIError(500, "IMPORT_FAILED", "CSV file has no header row.")
    headers = _resolve_headers(reader.fieldnames)

    household_ids = set(db.scalars(select(Household.id)).all())
    appliances = dict(
        db.execute(select(Appliance.name, Appliance.id)).all()
    )
    existing_keys = {
        (int(row[0]), int(row[1]), str(row[2]), str(row[3]))
        for row in db.execute(
            select(
                EnergyReading.household_id,
                EnergyReading.appliance_id,
                EnergyReading.reading_date,
                EnergyReading.reading_time,
            )
        ).all()
    }
    seen_keys = set(existing_keys)

    total_rows = 0
    inserted_rows = 0
    rejected_rows = 0
    duplicate_rows = 0
    quality_flagged_rows = 0
    new_household_ids: set[int] = set()
    affected_household_ids: set[int] = set()
    dimensions_dirty = False
    pending_rows: list[dict] = []
    dry_appliance_ids: dict[str, int] = {}

    def flush_dimensions() -> None:
        nonlocal dimensions_dirty
        if dimensions_dirty:
            db.flush()
            dimensions_dirty = False

    def flush_rows() -> None:
        nonlocal inserted_rows, dimensions_dirty
        if not pending_rows:
            return
        flush_dimensions()
        db.execute(insert(EnergyReading), pending_rows)
        inserted_rows += len(pending_rows)
        pending_rows.clear()
        dimensions_dirty = False

    for raw in reader:
        total_rows += 1
        try:
            parsed = _parse_row(raw, headers)
        except (TypeError, ValueError):
            rejected_rows += 1
            continue

        household_id = parsed["household_id"]
        appliance_name = parsed["appliance_name"]

        if household_id not in household_ids:
            household_ids.add(household_id)
            if not dry_run:
                db.add(
                    Household(
                        id=household_id,
                        display_name=f"Home {household_id}",
                    )
                )
                new_household_ids.add(household_id)
                dimensions_dirty = True

        appliance_id = appliances.get(appliance_name)
        if appliance_id is None:
            if dry_run:
                appliance_id = dry_appliance_ids.get(appliance_name)
                if appliance_id is None:
                    appliance_id = -1 - len(dry_appliance_ids)
                    dry_appliance_ids[appliance_name] = appliance_id
            else:
                appliance = Appliance(name=appliance_name)
                db.add(appliance)
                db.flush()
                appliance_id = int(appliance.id)
                appliances[appliance_name] = appliance_id

        key = (
            household_id,
            appliance_id,
            parsed["reading_date"],
            parsed["reading_time"],
        )
        if key in seen_keys:
            duplicate_rows += 1
            continue
        seen_keys.add(key)

        if parsed["quality_flag"] != "ok":
            quality_flagged_rows += 1

        if not dry_run:
            affected_household_ids.add(household_id)
            pending_rows.append(
                {
                    "household_id": household_id,
                    "appliance_id": appliance_id,
                    "reading_date": parsed["reading_date"],
                    "reading_time": parsed["reading_time"],
                    "energy_kwh": parsed["energy_kwh"],
                    "outdoor_temp_c": parsed["outdoor_temp_c"],
                    "season": parsed["season"],
                    "household_size": parsed["household_size"],
                    "quality_flag": parsed["quality_flag"],
                }
            )
            if len(pending_rows) >= IMPORT_CHUNK_SIZE:
                flush_rows()
        else:
            inserted_rows += 1

    flush_rows()

    if not dry_run:
        refresh_household_profiles(
            db, sorted(affected_household_ids | new_household_ids)
        )

    status = "dry_run" if dry_run else "completed"
    batch = ImportBatch(
        filename=filename,
        imported_at=datetime.now(UTC).astimezone().isoformat(timespec="seconds"),
        status=status,
        total_rows=total_rows,
        inserted_rows=inserted_rows,
        rejected_rows=rejected_rows,
        duplicate_rows=duplicate_rows,
        quality_flagged_rows=quality_flagged_rows,
    )
    db.add(batch)
    db.flush()

    return {
        "import_id": int(batch.id),
        "status": status,
        "filename": filename,
        "total_rows": total_rows,
        "inserted_rows": inserted_rows,
        "rejected_rows": rejected_rows,
        "duplicate_rows": duplicate_rows,
        "quality_flagged_rows": quality_flagged_rows,
    }


def import_csv_file(
    db: Session,
    path: str | Path,
    *,
    dry_run: bool = False,
) -> dict:
    file_path = Path(path)
    if not file_path.exists():
        raise APIError(
            500, "IMPORT_FAILED", f"CSV file was not found: {file_path}"
        )
    return import_csv(
        db,
        filename=file_path.name,
        raw_content=file_path.read_bytes(),
        dry_run=dry_run,
    )
