from pydantic import BaseModel


class ConsumptionSeriesItem(BaseModel):
    household_id: int
    display_name: str
    period: str
    kwh: float
    reading_count: int
    color_index: int


class ConsumptionSeriesMeta(BaseModel):
    unit: str = "kWh"
    max_households: int = 5
    excluded_appliance_ids: list[int] = []


class ConsumptionSeriesResponse(BaseModel):
    granularity: str
    start_date: str
    end_date: str
    items: list[ConsumptionSeriesItem]
    meta: ConsumptionSeriesMeta


class AveragePoint(BaseModel):
    period: str
    avg_kwh: float
    household_count: int
    expected_households: int


class AverageMeta(BaseModel):
    unit: str = "kWh"
    excluded_appliance_ids: list[int] = []


class AverageResponse(BaseModel):
    granularity: str
    scope: str
    items: list[AveragePoint]
    meta: AverageMeta


class BreakdownItem(BaseModel):
    appliance_id: int
    appliance_name: str
    kwh: float
    share: float


class BreakdownResponse(BaseModel):
    household_id: int
    start_date: str
    end_date: str
    total_kwh: float
    items: list[BreakdownItem]
