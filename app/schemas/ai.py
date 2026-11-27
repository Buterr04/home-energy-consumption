from pydantic import BaseModel, Field


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
    level_model: str = "LinearRegression"
    shape_model: str = "LinearRegression"


class PredictRequest(BaseModel):
    household_id: int
    month: int
    household_size: int
    forecast_monthly_temp_c: float | None = None


class PredictResponse(BaseModel):
    household_id: int
    month: int
    household_size: int
    predicted_avg_daily_kwh: float
    unit: str = "kWh/日"
    model_version: str
    average_daily_power_curve_kw: list[float] = Field(default_factory=list)
    monthly_energy_estimate_kwh: float | None = None
    temperature_used_c: float | None = None
    level_model: str = "LinearRegression"
    shape_model: str = "LinearRegression"
    warnings: list[str] = Field(default_factory=list)


class BatchPredictRequest(BaseModel):
    items: list[PredictRequest]


class BatchPredictItem(BaseModel):
    household_id: int
    month: int
    predicted_avg_daily_kwh: float


class BatchPredictResponse(BaseModel):
    model_version: str
    items: list[BatchPredictItem]
