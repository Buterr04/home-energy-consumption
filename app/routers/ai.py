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
from app.services.consumption import household_avg_daily_kwh
from app.services.model import model_registry

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


@router.get("/model", response_model=ModelInfo)
def model_info(
    _user: Annotated[User, Depends(get_current_user)],
) -> ModelInfo:
    info = model_registry.info()
    return ModelInfo(
        version=info["version"],
        trained_at=info.get("trained_at"),
        target=info.get("target", "avg_daily_kwh"),
        input_fields=info["input_fields"],
        features=info["features"],
        metrics=ModelMetrics(**info["metrics"]),
        training_rows=info.get("training_rows", 0),
        validation_rows=info.get("validation_rows", 0),
    )


@router.post("/predict", response_model=PredictResponse)
def predict(
    payload: PredictRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> PredictResponse:
    _validate_prediction_input(payload)
    ensure_household_access(db, user, [payload.household_id])
    info = model_registry.info()
    history = household_avg_daily_kwh(db, payload.household_id)
    predicted, warnings = model_registry.predict(
        household_id=payload.household_id,
        month=payload.month,
        household_size=payload.household_size,
        history_avg_daily_kwh=history,
    )

    return PredictResponse(
        household_id=payload.household_id,
        month=payload.month,
        household_size=payload.household_size,
        predicted_avg_daily_kwh=predicted,
        model_version=info["version"],
        warnings=warnings,
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
    info = model_registry.info()

    results = []
    for item in payload.items:
        history = household_avg_daily_kwh(db, item.household_id)
        predicted, _warnings = model_registry.predict(
            household_id=item.household_id,
            month=item.month,
            household_size=item.household_size,
            history_avg_daily_kwh=history,
        )
        results.append(
            BatchPredictItem(
                household_id=item.household_id,
                month=item.month,
                predicted_avg_daily_kwh=predicted,
            )
        )
    return BatchPredictResponse(model_version=info["version"], items=results)
