from typing import Literal

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
    forecast_monthly_temp_c: float


class PredictHistoryPoint(BaseModel):
    period: str
    actual_avg_daily_kwh: float
    temperature_c: float | None = None
    reading_days: int
    total_kwh: float


class PredictForecastPoint(BaseModel):
    period: str
    predicted_avg_daily_kwh: float
    temperature_used_c: float
    monthly_energy_estimate_kwh: float | None = None


class PredictResponse(BaseModel):
    household_id: int
    display_name: str
    month: int
    household_size: int
    anchor_month: str | None = None
    forecast_start_month: str | None = None
    forecast_end_month: str | None = None
    history_basis: Literal[
        "aggregate", "appliance_sum", "mixed", "none"
    ] = "none"
    history: list[PredictHistoryPoint] = Field(default_factory=list)
    forecast: list[PredictForecastPoint] = Field(default_factory=list)
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
    month: int
    predicted_avg_daily_kwh: float


class BatchPredictResponse(BaseModel):
    model_version: str
    items: list[BatchPredictItem]
