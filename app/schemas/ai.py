from pydantic import BaseModel


class ModelMetrics(BaseModel):
    mae: float | None = None
    rmse: float | None = None
    r2: float | None = None


class ModelInfo(BaseModel):
    version: str
    trained_at: str | None = None
    target: str = "avg_daily_kwh"
    input_fields: list[str]
    features: list[str]
    metrics: ModelMetrics
    training_rows: int = 0
    validation_rows: int = 0


class PredictRequest(BaseModel):
    household_id: int
    month: int
    household_size: int


class PredictResponse(BaseModel):
    household_id: int
    month: int
    household_size: int
    predicted_avg_daily_kwh: float
    unit: str = "kWh/日"
    model_version: str
    warnings: list[str] = []


class BatchPredictRequest(BaseModel):
    items: list[PredictRequest]


class BatchPredictItem(BaseModel):
    household_id: int
    month: int
    predicted_avg_daily_kwh: float


class BatchPredictResponse(BaseModel):
    model_version: str
    items: list[BatchPredictItem]
