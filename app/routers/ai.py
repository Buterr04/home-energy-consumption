import calendar
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import ensure_household_access, get_current_user
from app.errors import APIError
from app.models import User
from app.schemas.ai import (
    BatchPredictItem,
    BatchPredictRequest,
    BatchPredictResponse,
    ModelInfo,
    ModelMetrics,
    PredictForecastPoint,
    PredictHistoryPoint,
    PredictRequest,
    PredictResponse,
)
from app.services.consumption import (
    household_monthly_temp_profile,
    household_monthly_totals,
    household_summaries,
)
from app.services.linear_model import linear_model_registry

router = APIRouter(prefix="/ai", tags=["AI"])


def _validate_prediction_input(payload: PredictRequest) -> None:
    if payload.household_id < 1:
        raise APIError(
            400,
            "INVALID_HOUSEHOLD_ID",
            "household_id must be a positive integer.",
        )
    if not 1 <= payload.month <= 12:
        raise APIError(
            400, "INVALID_MONTH", "month must be an integer between 1 and 12."
        )
    if not 1 <= payload.household_size <= 20:
        raise APIError(
            400,
            "INVALID_HOUSEHOLD_SIZE",
            "household_size must be an integer between 1 and 20.",
        )
    if not -50 <= payload.forecast_monthly_temp_c <= 60:
        raise APIError(
            400,
            "INVALID_TEMPERATURE",
            "forecast_monthly_temp_c must be between -50 and 60.",
        )


def _period_from_index(index: int) -> str:
    year, month_zero_based = divmod(index, 12)
    return f"{year:04d}-{month_zero_based + 1:02d}"


def _history_basis(points: list[dict]) -> str:
    bases = {point["basis"] for point in points}
    if not bases:
        return "none"
    if len(bases) == 1:
        return next(iter(bases))
    return "mixed"


@router.get("/model", response_model=ModelInfo)
def model_info(
    _user: Annotated[User, Depends(get_current_user)],
) -> ModelInfo:
    info = linear_model_registry.info()
    return ModelInfo(
        version=info["version"],
        trained_at=info.get("trained_at"),
        target=info.get("target", "avg_daily_kwh"),
        input_fields=info["input_fields"],
        features=info["features"],
        metrics=ModelMetrics(**info["metrics"]),
        training_rows=info.get("training_rows", 0),
        validation_rows=info.get("validation_rows", 0),
        level_model=info.get("level_model", "LinearRegression"),
        shape_model=info.get("shape_model", "LinearRegression"),
    )


@router.post("/predict", response_model=PredictResponse)
def predict(
    payload: PredictRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> PredictResponse:
    _validate_prediction_input(payload)
    ensure_household_access(db, user, [payload.household_id])
    summaries = household_summaries(db, [payload.household_id])
    summary = summaries.get(payload.household_id)
    if summary is None:
        raise APIError(
            404, "HOUSEHOLD_NOT_FOUND", "The household does not exist."
        )

    last_date = (
        date.fromisoformat(summary["last_date"])
        if summary.get("last_date")
        else date.today()
    )
    anchor_index = last_date.year * 12 + last_date.month - 1
    history_start_index = anchor_index - 11
    history_start = date(
        history_start_index // 12,
        history_start_index % 12 + 1,
        1,
    )
    history_end = date(
        last_date.year,
        last_date.month,
        calendar.monthrange(last_date.year, last_date.month)[1],
    )
    history = household_monthly_totals(
        db, payload.household_id, history_start, history_end
    )
    history_basis = _history_basis(history)

    month_offset = (payload.month - last_date.month) % 12 or 12
    forecast_start_index = anchor_index + month_offset
    temp_profile = household_monthly_temp_profile(db, payload.household_id)
    fallback_temp = float(summary.get("avg_temp_c") or 15.0)
    info = linear_model_registry.info()

    warnings: list[str] = []
    if month_offset > 1:
        warnings.append(
            "The forecast start is not immediately after the last reading; "
            "the chart may show a gap before the forecast."
        )

    forecast: list[PredictForecastPoint] = []
    first_result: dict | None = None
    for offset in range(6):
        period_index = forecast_start_index + offset
        period = _period_from_index(period_index)
        month = int(period[5:7])
        year = int(period[:4])
        temperature = (
            payload.forecast_monthly_temp_c
            if offset == 0
            else temp_profile.get(month, fallback_temp)
        )
        result = linear_model_registry.predict(
            month=month,
            household_size=payload.household_size,
            outdoor_temp_c=temperature,
            year=year,
        )
        warnings.extend(result["warnings"])
        if first_result is None:
            first_result = result
        forecast.append(
            PredictForecastPoint(
                period=period,
                predicted_avg_daily_kwh=result[
                    "daily_average_energy_kwh"
                ],
                temperature_used_c=round(temperature, 2),
                monthly_energy_estimate_kwh=result[
                    "monthly_energy_estimate_kwh"
                ],
            )
        )

    if first_result is None:  # pragma: no cover - defensive
        raise APIError(503, "MODEL_NOT_READY", "The linear model is not ready.")

    return PredictResponse(
        household_id=payload.household_id,
        display_name=summary["display_name"],
        month=payload.month,
        household_size=payload.household_size,
        anchor_month=(summary.get("last_date") or "")[:7] or None,
        forecast_start_month=forecast[0].period,
        forecast_end_month=forecast[-1].period,
        history_basis=history_basis,
        history=[
            PredictHistoryPoint(
                period=point["period"],
                actual_avg_daily_kwh=point["actual_avg_daily_kwh"],
                temperature_c=point["temperature_c"],
                reading_days=point["reading_days"],
                total_kwh=point["total_kwh"],
            )
            for point in history
        ],
        forecast=forecast,
        predicted_avg_daily_kwh=first_result["daily_average_energy_kwh"],
        model_version=info["version"],
        average_daily_power_curve_kw=first_result[
            "average_daily_power_curve_kw"
        ],
        monthly_energy_estimate_kwh=first_result[
            "monthly_energy_estimate_kwh"
        ],
        temperature_used_c=round(payload.forecast_monthly_temp_c, 2),
        level_model=first_result["level_model"],
        shape_model=first_result["shape_model"],
        warnings=list(dict.fromkeys(warnings)),
    )


@router.post("/predict/batch", response_model=BatchPredictResponse)
def predict_batch(
    payload: BatchPredictRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> BatchPredictResponse:
    if not payload.items:
        raise APIError(
            422, "VALIDATION_ERROR", "At least one prediction item is required."
        )
    for item in payload.items:
        _validate_prediction_input(item)
        ensure_household_access(db, user, [item.household_id])
    info = linear_model_registry.info()

    results = []
    for item in payload.items:
        result = linear_model_registry.predict(
            month=item.month,
            household_size=item.household_size,
            outdoor_temp_c=item.forecast_monthly_temp_c,
        )
        results.append(
            BatchPredictItem(
                month=item.month,
                predicted_avg_daily_kwh=result["daily_average_energy_kwh"],
            )
        )
    return BatchPredictResponse(model_version=info["version"], items=results)
