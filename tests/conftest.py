import os
import sqlite3
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

TEST_ROOT = Path(tempfile.mkdtemp(prefix="home-energy-tests-"))
TEST_DB = TEST_ROOT / "test.db"
TEST_MODEL = TEST_ROOT / "model.joblib"

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["MODEL_PATH"] = str(TEST_MODEL)
os.environ["JWT_SECRET"] = "test-only-secret-that-is-at-least-32-bytes"

from fastapi.testclient import TestClient  # noqa: E402

from app.config import BASE_DIR  # noqa: E402
from app.database import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Household, User  # noqa: E402
from app.security import hash_password  # noqa: E402
from app.services.imports import import_csv  # noqa: E402

MINI_CSV = (
    "Home ID,Appliance Type,Energy Consumption (kWh),Time,Date,"
    "Outdoor Temperature (°C),Season,Household Size\n"
    "1,Fridge,1.0,10:00,2023-12-01,4.0,Winter,3\n"
    "1,Heater,2.0,11:00,2023-12-01,4.0,Winter,3\n"
    "1,Fridge,0.8,10:00,2023-12-02,4.0,Winter,3\n"
    "1,Heater,1.8,11:00,2023-12-02,4.0,Winter,3\n"
    "2,Fridge,0.5,10:00,2023-12-01,12.0,Spring,2\n"
    "2,Fridge,0.4,10:00,2023-12-02,12.0,Spring,2\n"
    "2,Fridge,0.6,10:00,2023-12-03,12.0,Spring,2\n"
    "3,Fridge,0.7,10:00,2023-12-02,20.0,Summer,4\n"
)


@pytest.fixture(scope="session", autouse=True)
def model_artifact() -> Path:
    import joblib
    import pandas as pd
    from sklearn.compose import ColumnTransformer
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder

    frame = pd.DataFrame(
        {
            "household_id": [1, 1, 2, 2, 3, 3],
            "month": [1, 6, 2, 7, 10, 11],
            "household_size": [3, 3, 2, 2, 4, 4],
            "history_avg_daily_kwh": [2.5, 2.5, 1.2, 1.2, 0.8, 0.8],
            "season": ["Winter", "Summer", "Winter", "Summer", "Fall", "Fall"],
        }
    )
    target = [2.4, 2.6, 1.1, 1.3, 0.7, 0.9]
    pipeline = Pipeline(
        [
            (
                "features",
                ColumnTransformer(
                    [
                        (
                            "season",
                            OneHotEncoder(handle_unknown="ignore"),
                            ["season"],
                        ),
                        (
                            "numeric",
                            "passthrough",
                            [
                                "household_id",
                                "month",
                                "household_size",
                                "history_avg_daily_kwh",
                            ],
                        ),
                    ]
                ),
            ),
            ("model", RandomForestRegressor(n_estimators=20, random_state=7)),
        ]
    )
    pipeline.fit(frame, target)
    bundle = {
        "pipeline": pipeline,
        "metadata": {
            "version": "test-rf",
            "trained_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "target": "avg_daily_kwh",
            "input_fields": ["household_id", "month", "household_size"],
            "features": [
                "household_id",
                "month",
                "household_size",
                "history_avg_daily_kwh",
                "season",
            ],
            "feature_columns": [
                "household_id",
                "month",
                "household_size",
                "history_avg_daily_kwh",
                "season",
            ],
            "metrics": {"mae": 0.2, "rmse": 0.3, "r2": 0.8},
            "training_rows": 4,
            "validation_rows": 2,
            "fallback_history": 1.5,
        },
    }
    joblib.dump(bundle, TEST_MODEL)
    return TEST_MODEL


@pytest.fixture(scope="session", autouse=True)
def seeded_database(model_artifact: Path):
    with sqlite3.connect(TEST_DB) as connection:
        for schema_file in (BASE_DIR / "db" / "01_business.sql",):
            connection.executescript(schema_file.read_text(encoding="utf-8"))
        connection.commit()

    db = SessionLocal()
    try:
        admin = User(
            username="admin",
            password_hash=hash_password("admin123"),
            display_name="Administrator",
            role="admin",
            is_active=True,
        )
        demo1 = User(
            username="demo1",
            password_hash=hash_password("demo123"),
            display_name="Demo 1",
            role="user",
            is_active=True,
        )
        demo2 = User(
            username="demo2",
            password_hash=hash_password("demo123"),
            display_name="Demo 2",
            role="user",
            is_active=True,
        )
        db.add_all([admin, demo1, demo2])
        db.flush()
        import_csv(db, filename="mini.csv", raw_content=MINI_CSV)
        db.flush()
        for household_id in (1, 2):
            household = db.get(Household, household_id)
            household.owner_user_id = demo1.id
        household = db.get(Household, 3)
        household.owner_user_id = demo2.id
        db.commit()
    finally:
        db.close()

    yield
    engine.dispose()


@pytest.fixture(scope="session")
def client(seeded_database, model_artifact) -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def demo_token(client: TestClient) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "demo1", "password": "demo123"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture(scope="session")
def admin_token(client: TestClient) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]
