from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("1")
    )
    created_at: Mapped[str] = mapped_column(
        String, nullable=False, server_default=text("(datetime('now'))")
    )

    __table_args__ = (
        CheckConstraint("role IN ('user', 'admin')", name="ck_users_role"),
    )

    @property
    def role_label(self) -> str:
        return self.role


class Household(Base):
    __tablename__ = "households"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    display_name: Mapped[str | None] = mapped_column(String, nullable=True)
    city: Mapped[str] = mapped_column(
        String, nullable=False, server_default=text("'Chengdu'")
    )
    created_at: Mapped[str] = mapped_column(
        String, nullable=False, server_default=text("(datetime('now'))")
    )

    __table_args__ = (
        CheckConstraint("id > 0", name="ck_households_id_positive"),
        Index("idx_households_owner", "owner_user_id"),
    )


class Appliance(Base):
    __tablename__ = "appliances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    created_at: Mapped[str] = mapped_column(
        String, nullable=False, server_default=text("(datetime('now'))")
    )


class EnergyReading(Base):
    __tablename__ = "energy_readings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    household_id: Mapped[int] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False
    )
    appliance_id: Mapped[int] = mapped_column(
        ForeignKey("appliances.id", ondelete="RESTRICT"), nullable=False
    )
    reading_date: Mapped[str] = mapped_column(String, nullable=False)
    reading_time: Mapped[str] = mapped_column(String, nullable=False)
    energy_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    outdoor_temp_c: Mapped[float] = mapped_column(Float, nullable=False)
    season: Mapped[str] = mapped_column(String, nullable=False)
    household_size: Mapped[int] = mapped_column(Integer, nullable=False)
    quality_flag: Mapped[str] = mapped_column(
        String, nullable=False, default="ok", server_default=text("'ok'")
    )
    created_at: Mapped[str] = mapped_column(
        String, nullable=False, server_default=text("(datetime('now'))")
    )

    __table_args__ = (
        UniqueConstraint(
            "household_id",
            "appliance_id",
            "reading_date",
            "reading_time",
            name="uq_readings_identity",
        ),
        CheckConstraint("energy_kwh >= 0", name="ck_readings_energy_non_negative"),
        CheckConstraint(
            "household_size BETWEEN 1 AND 20", name="ck_readings_household_size"
        ),
        CheckConstraint(
            "season IN ('Winter', 'Spring', 'Summer', 'Fall')",
            name="ck_readings_season",
        ),
        Index("idx_readings_home_date", "household_id", "reading_date"),
        Index("idx_readings_date_appliance", "reading_date", "appliance_id"),
        Index("idx_readings_quality", "quality_flag", "reading_date"),
    )


class HouseholdProfile(Base):
    __tablename__ = "household_profiles"

    household_id: Mapped[int] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), primary_key=True
    )
    size_median: Mapped[float | None] = mapped_column(Float, nullable=True)
    size_mode: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_temp_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_daily_kwh: Mapped[float | None] = mapped_column(Float, nullable=True)
    reading_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    first_date: Mapped[str | None] = mapped_column(String, nullable=True)
    last_date: Mapped[str | None] = mapped_column(String, nullable=True)
    updated_at: Mapped[str] = mapped_column(
        String, nullable=False, server_default=text("(datetime('now'))")
    )


class ImportBatch(Base):
    __tablename__ = "import_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    imported_at: Mapped[str] = mapped_column(String, nullable=False)
    total_rows: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    inserted_rows: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    rejected_rows: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    duplicate_rows: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    quality_flagged_rows: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    status: Mapped[str] = mapped_column(
        String, nullable=False, default="running", server_default=text("'running'")
    )
