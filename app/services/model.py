import threading
from pathlib import Path

from app.config import get_settings
from app.errors import APIError

MONTH_TO_SEASON = {
    12: "Winter",
    1: "Winter",
    2: "Winter",
    3: "Spring",
    4: "Spring",
    5: "Spring",
    6: "Summer",
    7: "Summer",
    8: "Summer",
    9: "Fall",
    10: "Fall",
    11: "Fall",
}


class ModelRegistry:
    def __init__(self) -> None:
        self._bundle: dict | None = None
        self._load_error: str | None = None
        self._lock = threading.Lock()

    @property
    def ready(self) -> bool:
        return self._bundle is not None

    def load(self, path: str | Path | None = None) -> bool:
        settings = get_settings()
        artifact_path = Path(path or settings.model_path)
        with self._lock:
            if not artifact_path.exists():
                self._bundle = None
                self._load_error = f"Model artifact was not found: {artifact_path}"
                return False
            try:
                import joblib

                bundle = joblib.load(artifact_path)
                if not isinstance(bundle, dict) or "pipeline" not in bundle:
                    raise ValueError("The model artifact has an invalid format.")
                self._bundle = bundle
                self._load_error = None
                return True
            except Exception as exc:  # pragma: no cover - depends on local artifact
                self._bundle = None
                self._load_error = str(exc)
                return False

    def _require_bundle(self) -> dict:
        if self._bundle is None:
            self.load()
        if self._bundle is None:
            message = self._load_error or "The model is not ready."
            raise APIError(503, "MODEL_NOT_READY", message)
        return self._bundle

    def info(self) -> dict:
        bundle = self._require_bundle()
        metadata = bundle.get("metadata", {})
        metrics = metadata.get("metrics", {})
        return {
            "version": metadata.get("version", get_settings().model_version),
            "trained_at": metadata.get("trained_at"),
            "target": metadata.get("target", "avg_daily_kwh"),
            "input_fields": metadata.get(
                "input_fields",
                ["household_id", "month", "household_size"],
            ),
            "features": metadata.get(
                "features",
                [
                    "household_id",
                    "month",
                    "household_size",
                    "history_avg_daily_kwh",
                    "season",
                ],
            ),
            "metrics": {
                "mae": metrics.get("mae"),
                "rmse": metrics.get("rmse"),
                "r2": metrics.get("r2"),
            },
            "training_rows": metadata.get("training_rows", 0),
            "validation_rows": metadata.get("validation_rows", 0),
        }

    def predict(
        self,
        *,
        household_id: int,
        month: int,
        household_size: int,
        history_avg_daily_kwh: float | None,
    ) -> tuple[float, list[str]]:
        bundle = self._require_bundle()
        metadata = bundle.get("metadata", {})
        warnings: list[str] = []
        history = history_avg_daily_kwh
        if history is None:
            history = float(metadata.get("fallback_history", 0.0))
            warnings.append(
                "Household history is unavailable; a global fallback was used."
            )

        import pandas as pd

        columns = metadata.get(
            "feature_columns",
            [
                "household_id",
                "month",
                "household_size",
                "history_avg_daily_kwh",
                "season",
            ],
        )
        frame = pd.DataFrame(
            [
                {
                    "household_id": household_id,
                    "month": month,
                    "household_size": household_size,
                    "history_avg_daily_kwh": float(history),
                    "season": MONTH_TO_SEASON[month],
                }
            ],
            columns=columns,
        )
        prediction = float(bundle["pipeline"].predict(frame)[0])
        return round(max(0.0, prediction), 2), warnings


model_registry = ModelRegistry()
