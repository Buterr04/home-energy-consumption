from pydantic import BaseModel


class HouseholdSummary(BaseModel):
    household_id: int
    display_name: str
    size_median: float | None
    avg_temp_c: float | None
    avg_daily_kwh: float | None
    reading_count: int
    first_date: str | None
    last_date: str | None
    owner_user_id: int | None = None


class HouseholdAppliance(BaseModel):
    appliance_id: int
    appliance_name: str
    reading_count: int


class HouseholdDetail(HouseholdSummary):
    appliances: list[HouseholdAppliance]


class ApplianceStat(BaseModel):
    appliance_id: int
    name: str
    reading_count: int
    avg_energy_kwh: float | None


class ApplianceListResponse(BaseModel):
    items: list[ApplianceStat]
