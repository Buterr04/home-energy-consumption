from __future__ import annotations

import calendar
import json
import threading
from datetime import date
from pathlib import Path

import numpy as np

from app.config import get_settings
from app.errors import APIError

HOURS = range(24)
MONTHS = range(1, 13)


def _normalize(values: np.ndarray) -> np.ndarray:
    values = np.clip(np.asarray(values, dtype=float), 0.0, None)
    total = float(values.sum())
    if total > 0:
        return values / total
    return np.full(24, 1.0 / 24.0)


class LinearModelRegistry:
    def __init__(self) -> None:
        self._stage1: dict | None = None
        self._stage2: dict | None = None
        self._metadata: dict = {}
        self._load_error: str | None = None
        self._lock = threading.Lock()

    @property
    def ready(self) -> bool:
        return self._stage1 is not None and self._stage2 is not None

    def load(self, model_dir: str | Path | None = None) -> bool:
        settings = get_settings()
        base = Path(model_dir or settings.linear_model_dir)
        with self._lock:
            self._stage1 = None
            self._stage2 = None
            self._metadata = {}
            if not base.is_dir():
                self._load_error = f"Linear model directory was not found: {base}"
                return False
            try:
                import joblib

                stage1 = joblib.load(base / "stage1_linear.joblib")
                stage2 = joblib.load(base / "stage2_linear.joblib")
                self._validate_stage1(stage1)
                self._validate_stage2(stage2)
                metadata_path = base / "metadata.json"
                metadata: dict = {}
                if metadata_path.exists():
                    metadata = json.loads(
                        metadata_path.read_text(encoding="utf-8")
                    )
                self._stage1 = stage1
                self._stage2 = stage2
                self._metadata = metadata
                self._load_error = None
                return True
            except Exception as exc:  # pragma: no cover - local artifact
                self._load_error = str(exc)
                return False

    @staticmethod
    def _validate_stage1(stage1: dict) -> None:
        if not isinstance(stage1, dict) or "model" not in stage1:
            raise ValueError("stage1_linear.joblib has an invalid format.")
        if getattr(stage1["model"], "n_features_in_", None) != 3:
            raise ValueError("stage1_linear.joblib expects three features.")

    @staticmethod
    def _validate_stage2(stage2: dict) -> None:
        if (
            not isinstance(stage2, dict)
            or "model" not in stage2
            or "columns" not in stage2
        ):
            raise ValueError("stage2_linear.joblib has an invalid format.")
        columns = list(stage2["columns"])
        model = stage2["model"]
        if getattr(model, "n_features_in_", None) != len(columns):
            raise ValueError(
                "stage2_linear.joblib feature columns do not match the model."
            )
        expected = {
            "Outdoor Temperature (°C)",
            "Household Size",
            *(f"m_{month}" for month in MONTHS),
            *(f"h_{hour}" for hour in HOURS),
            *(
                f"mh_{month}_{hour}"
                for month in MONTHS
                for hour in HOURS
            ),
        }
        missing = expected.difference(columns)
        if missing:
            raise ValueError(
                "stage2_linear.joblib is missing feature columns: "
                + ", ".join(sorted(missing))
            )

    def _require_models(self) -> tuple[dict, dict]:
        if not self.ready:
            self.load()
        if not self.ready:
            message = self._load_error or "The linear model is not ready."
            raise APIError(503, "MODEL_NOT_READY", message)
        return self._stage1, self._stage2  # type: ignore[return-value]

    def info(self) -> dict:
        stage1, _stage2 = self._require_models()
        metadata = self._metadata
        metrics = metadata.get("metrics") or {}
        settings = get_settings()
        return {
            "version": str(metadata.get("version") or settings.model_version),
            "trained_at": metadata.get("trained_at"),
            "target": metadata.get("target", "avg_daily_kwh"),
            "input_fields": metadata.get(
                "input_fields",
                ["month", "household_size", "forecast_monthly_temp_c"],
            ),
            "features": metadata.get(
                "features", list(stage1.get("features", []))
            ),
            "metrics": {
                "mae": metrics.get("mae"),
                "rmse": metrics.get("rmse"),
                "r2": metrics.get("r2"),
            },
            "training_rows": int(metadata.get("training_rows") or 0),
            "validation_rows": int(metadata.get("validation_rows") or 0),
            "level_model": "LinearRegression",
            "shape_model": "LinearRegression",
        }

    def _design_matrix(
        self,
        *,
        outdoor_temp_c: float,
        household_size: int,
        month: int,
    ) -> np.ndarray:
        _stage1, stage2 = self._require_models()
        columns = list(stage2["columns"])
        rows: list[list[float]] = []
        for hour in HOURS:
            values = {
                "Outdoor Temperature (°C)": float(outdoor_temp_c),
                "Household Size": float(household_size),
            }
            for candidate_month in MONTHS:
                values[f"m_{candidate_month}"] = (
                    1.0 if month == candidate_month else 0.0
                )
            for candidate_hour in HOURS:
                values[f"h_{candidate_hour}"] = (
                    1.0 if hour == candidate_hour else 0.0
                )
            for candidate_month in MONTHS:
                for candidate_hour in HOURS:
                    values[f"mh_{candidate_month}_{candidate_hour}"] = (
                        1.0
                        if month == candidate_month
                        and hour == candidate_hour
                        else 0.0
                    )
            rows.append([values[column] for column in columns])
        return np.asarray(rows, dtype=float)

    def predict(
        self,
        *,
        month: int,
        household_size: int,
        outdoor_temp_c: float,
        year: int | None = None,
    ) -> dict:
        if month not in MONTHS:
            raise ValueError("month must be between 1 and 12.")
        if household_size < 1:
            raise ValueError("household_size must be at least 1.")

        stage1, stage2 = self._require_models()
        warnings: list[str] = []

        daily_energy = float(
            stage1["model"].predict(
                [[float(outdoor_temp_c), float(household_size), float(month)]]
            )[0]
        )
        if daily_energy < 0:
            daily_energy = 0.0
            warnings.append(
                "The level model returned a negative value; it was clamped to zero."
            )

        shares = _normalize(
            stage2["model"].predict(
                self._design_matrix(
                    outdoor_temp_c=outdoor_temp_c,
                    household_size=household_size,
                    month=month,
                )
            )
        )
        curve = shares * daily_energy
        days = calendar.monthrange(
            year or date.today().year, month
        )[1]

        return {
            "daily_average_energy_kwh": round(daily_energy, 3),
            "average_daily_power_curve_kw": [
                round(float(value), 4) for value in curve
            ],
            "monthly_energy_estimate_kwh": round(daily_energy * days, 1),
            "days_assumed": days,
            "level_model": "LinearRegression",
            "shape_model": "LinearRegression",
            "warnings": warnings,
        }


linear_model_registry = LinearModelRegistry()
