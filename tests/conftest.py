import json
import os
import sqlite3
import tempfile
from pathlib import Path

import pytest

TEST_ROOT = Path(tempfile.mkdtemp(prefix="home-energy-tests-"))
TEST_DB = TEST_ROOT / "test.db"
TEST_LINEAR_DIR = TEST_ROOT / "linear"

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["LINEAR_MODEL_DIR"] = str(TEST_LINEAR_DIR)
os.environ["MODEL_VERSION"] = "test-linear"
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
    import numpy as np
    from sklearn.linear_model import LinearRegression

    TEST_LINEAR_DIR.mkdir(parents=True, exist_ok=True)

    stage1_features = [
        "Outdoor Temperature (°C)",
        "Household Size",
        "Month",
    ]
    stage1_frame = np.asarray(
        [
            [4.0, 3, 12],
            [12.0, 2, 4],
            [20.0, 4, 7],
            [15.0, 1, 10],
            [8.0, 5, 2],
            [26.0, 2, 8],
        ]
    )
    stage1_target = [3.2, 2.6, 1.8, 2.0, 3.4, 2.2]
    stage1_model = LinearRegression().fit(stage1_frame, stage1_target)
    joblib.dump(
        {
            "model": stage1_model,
            "features": stage1_features,
            "target": "Daily Average Energy (kWh/day)",
        },
        TEST_LINEAR_DIR / "stage1_linear.joblib",
    )

    columns = [
        "Outdoor Temperature (°C)",
        "Household Size",
        *(f"m_{month}" for month in range(1, 13)),
        *(f"h_{hour}" for hour in range(24)),
        *(
            f"mh_{month}_{hour}"
            for month in range(1, 13)
            for hour in range(24)
        ),
    ]
    rows = []
    for hour in range(24):
        values = {
            "Outdoor Temperature (°C)": 12.0,
            "Household Size": 3.0,
            **{f"m_{month}": float(month == 12) for month in range(1, 13)},
            **{f"h_{item}": float(item == hour) for item in range(24)},
            **{
                f"mh_{month}_{item}": float(
                    month == 12 and item == hour
                )
                for month in range(1, 13)
                for item in range(24)
            },
        }
        rows.append([values[column] for column in columns])
    shares = 1 / 24 + np.sin((np.arange(24) - 6) / 24 * 2 * np.pi) * 0.005
    stage2_model = LinearRegression().fit(np.asarray(rows), shares)
    joblib.dump(
        {
            "type": "long",
            "columns": columns,
            "model": stage2_model,
            "input_features": [
                "Outdoor Temperature (°C)",
                "Household Size",
                "Month",
            ],
            "output": "hourly share",
        },
        TEST_LINEAR_DIR / "stage2_linear.joblib",
    )
    (TEST_LINEAR_DIR / "metadata.json").write_text(
        json.dumps(
            {
                "version": "test-linear",
                "trained_at": None,
                "target": "avg_daily_kwh",
                "input_fields": [
                    "month",
                    "household_size",
                    "forecast_monthly_temp_c",
                ],
                "features": stage1_features,
                "metrics": {"mae": 0.2, "rmse": 0.3, "r2": 0.8},
                "training_rows": 4,
                "validation_rows": 2,
            }
        ),
        encoding="utf-8",
    )
    return TEST_LINEAR_DIR


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
