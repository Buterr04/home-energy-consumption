import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from app.config import BASE_DIR, get_settings
from app.scripts.paths import find_default_dataset
from app.services.model import MONTH_TO_SEASON

NUMERIC_FEATURES = [
    "household_id",
    "month",
    "household_size",
    "history_avg_daily_kwh",
]
FEATURE_COLUMNS = NUMERIC_FEATURES + ["season"]


def _find_column(columns: list[str], prefix: str) -> str:
    for column in columns:
        if column.strip().lower().startswith(prefix):
            return column
    raise ValueError(f"Missing CSV column: {prefix}")


def build_training_frame(csv_path: Path) -> pd.DataFrame:
    data = pd.read_csv(csv_path, encoding="latin-1")
    columns = list(data.columns)
    column_map = {
        _find_column(columns, "home id"): "household_id",
        _find_column(columns, "appliance type"): "appliance_name",
        _find_column(columns, "energy consumption"): "energy_kwh",
        _find_column(columns, "date"): "reading_date",
        _find_column(columns, "household size"): "household_size_raw",
    }
    data = data.rename(columns=column_map)
    data["reading_date"] = pd.to_datetime(
        data["reading_date"], format="%Y-%m-%d", errors="raise"
    )
    data["month"] = data["reading_date"].dt.month.astype(int)
    data["household_id"] = data["household_id"].astype(int)
    data["energy_kwh"] = data["energy_kwh"].astype(float)
    data["household_size_raw"] = data["household_size_raw"].astype(int)

    home_daily = (
        data.groupby(["household_id", "reading_date"], as_index=False)
        .agg(
            energy_kwh=("energy_kwh", "sum"),
            household_size=("household_size_raw", "median"),
        )
    )
    home_daily["month"] = home_daily["reading_date"].dt.month.astype(int)

    monthly = (
        home_daily.groupby(["household_id", "month"], as_index=False)
        .agg(
            avg_daily_kwh=("energy_kwh", "mean"),
            month_kwh=("energy_kwh", "sum"),
            month_days=("reading_date", "count"),
            household_size=("household_size", "median"),
        )
    )
    household_total = (
        home_daily.groupby("household_id", as_index=False)
        .agg(
            total_kwh=("energy_kwh", "sum"),
            total_days=("reading_date", "count"),
        )
    )
    monthly = monthly.merge(household_total, on="household_id", how="left")
    monthly["history_avg_daily_kwh"] = (
        (monthly["total_kwh"] - monthly["month_kwh"])
        / (monthly["total_days"] - monthly["month_days"]).replace(0, np.nan)
    )
    monthly["history_avg_daily_kwh"] = monthly[
        "history_avg_daily_kwh"
    ].fillna(monthly["total_kwh"] / monthly["total_days"])
    monthly["season"] = monthly["month"].map(MONTH_TO_SEASON)
    result = monthly[FEATURE_COLUMNS + ["avg_daily_kwh"]].copy()
    result.attrs["train_start"] = str(data["reading_date"].min().date())
    result.attrs["train_end"] = str(data["reading_date"].max().date())
    return result


def train_and_save(
    *,
    csv_path: Path,
    output_path: Path,
    version: str,
) -> dict:
    frame = build_training_frame(csv_path)
    train, validation = train_test_split(
        frame, test_size=0.2, random_state=42
    )

    pipeline = Pipeline(
        steps=[
            (
                "features",
                ColumnTransformer(
                    transformers=[
                        (
                            "season",
                            OneHotEncoder(handle_unknown="ignore"),
                            ["season"],
                        ),
                        ("numeric", "passthrough", NUMERIC_FEATURES),
                    ]
                ),
            ),
            (
                "model",
                RandomForestRegressor(
                    n_estimators=220,
                    min_samples_leaf=2,
                    random_state=42,
                    n_jobs=-1,
                ),
            ),
        ]
    )
    pipeline.fit(train[FEATURE_COLUMNS], train["avg_daily_kwh"])

    predictions = pipeline.predict(validation[FEATURE_COLUMNS])
    metrics = {
        "mae": round(
            float(mean_absolute_error(validation["avg_daily_kwh"], predictions)),
            4,
        ),
        "rmse": round(
            float(
                np.sqrt(
                    mean_squared_error(
                        validation["avg_daily_kwh"], predictions
                    )
                )
            ),
            4,
        ),
        "r2": round(float(r2_score(validation["avg_daily_kwh"], predictions)), 4),
    }

    train_start = frame.attrs.get("train_start")
    train_end = frame.attrs.get("train_end")

    metadata = {
        "version": version,
        "trained_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(
            timespec="seconds"
        ),
        "target": "avg_daily_kwh",
        "input_fields": ["household_id", "month", "household_size"],
        "features": FEATURE_COLUMNS,
        "feature_columns": FEATURE_COLUMNS,
        "numeric_features": NUMERIC_FEATURES,
        "metrics": metrics,
        "training_rows": int(len(train)),
        "validation_rows": int(len(validation)),
        "train_start": train_start,
        "train_end": train_end,
        "fallback_history": float(frame["history_avg_daily_kwh"].mean()),
    }
    bundle = {"pipeline": pipeline, "metadata": metadata}

    output_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, output_path)

    return {
        "artifact": str(output_path),
        "metadata": metadata,
    }


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Train the offline model artifact.")
    parser.add_argument("--csv", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=Path(settings.model_path))
    parser.add_argument("--version", default=settings.model_version)
    args = parser.parse_args()

    csv_path = args.csv or find_default_dataset()
    if csv_path is None:
        raise SystemExit(
            f"Dataset not found under {BASE_DIR}. Pass --csv or set DATASET_PATH."
        )

    result = train_and_save(
        csv_path=csv_path,
        output_path=args.output,
        version=args.version,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
