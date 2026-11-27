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
    PredictRequest,
    PredictResponse,
)
from app.services.consumption import household_month_avg_temp_c
from app.services.linear_model import linear_model_registry

router = APIRouter(prefix="/ai", tags=["AI"])


def _validate_prediction_input(payload: PredictRequest) -> None:
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
    if (
        payload.forecast_monthly_temp_c is not None
        and not -50 <= payload.forecast_monthly_temp_c <= 60
    ):
        raise APIError(
            400,
            "INVALID_TEMPERATURE",
            "forecast_monthly_temp_c must be between -50 and 60.",
        )


def _resolve_temperature(
    db: Session, payload: PredictRequest
) -> tuple[float, list[str]]:
    if payload.forecast_monthly_temp_c is not None:
        return float(payload.forecast_monthly_temp_c), []
    temperature, warning = household_month_avg_temp_c(
        db, payload.household_id, payload.month
    )
    return temperature, [warning] if warning else []


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
    info = linear_model_registry.info()
    temperature, temperature_warnings = _resolve_temperature(db, payload)
    result = linear_model_registry.predict(
        month=payload.month,
        household_size=payload.household_size,
        outdoor_temp_c=temperature,
    )

    return PredictResponse(
        household_id=payload.household_id,
        month=payload.month,
        household_size=payload.household_size,
        predicted_avg_daily_kwh=result["daily_average_energy_kwh"],
        model_version=info["version"],
        average_daily_power_curve_kw=result[
            "average_daily_power_curve_kw"
        ],
        monthly_energy_estimate_kwh=result["monthly_energy_estimate_kwh"],
        temperature_used_c=round(temperature, 2),
        level_model=result["level_model"],
        shape_model=result["shape_model"],
        warnings=temperature_warnings + result["warnings"],
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
    ids = list(dict.fromkeys(item.household_id for item in payload.items))
    ensure_household_access(db, user, ids)
    info = linear_model_registry.info()

    results = []
    temperature_cache: dict[tuple[int, int], float] = {}
    for item in payload.items:
        cache_key = (item.household_id, item.month)
        temperature = temperature_cache.get(cache_key)
        if temperature is None:
            temperature, _warning = _resolve_temperature(db, item)
            temperature_cache[cache_key] = temperature
        result = linear_model_registry.predict(
            month=item.month,
            household_size=item.household_size,
            outdoor_temp_c=temperature,
        )
        results.append(
            BatchPredictItem(
                household_id=item.household_id,
                month=item.month,
                predicted_avg_daily_kwh=result["daily_average_energy_kwh"],
            )
        )
    return BatchPredictResponse(model_version=info["version"], items=results)
