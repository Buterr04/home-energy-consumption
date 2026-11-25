from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Appliance, EnergyReading, User
from app.schemas.household import ApplianceListResponse, ApplianceStat

router = APIRouter(prefix="/appliances", tags=["Appliances"])


@router.get("", response_model=ApplianceListResponse)
def list_appliances(
    _user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ApplianceListResponse:
    rows = db.execute(
        select(
            Appliance.id.label("appliance_id"),
            Appliance.name.label("name"),
            func.count(EnergyReading.id).label("reading_count"),
            func.avg(EnergyReading.energy_kwh).label("avg_energy_kwh"),
        )
        .outerjoin(EnergyReading, EnergyReading.appliance_id == Appliance.id)
        .group_by(Appliance.id, Appliance.name)
        .order_by(Appliance.id)
    ).all()
    return ApplianceListResponse(
        items=[
            ApplianceStat(
                appliance_id=int(row.appliance_id),
                name=row.name,
                reading_count=int(row.reading_count),
                avg_energy_kwh=round(float(row.avg_energy_kwh), 3)
                if row.avg_energy_kwh is not None
                else None,
            )
            for row in rows
        ]
    )
