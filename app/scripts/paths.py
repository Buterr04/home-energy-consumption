import os
from pathlib import Path

from app.config import BASE_DIR


def find_default_dataset() -> Path | None:
    env_path = os.getenv("DATASET_PATH")
    candidates = []
    if env_path:
        candidates.append(Path(env_path).expanduser())
    candidates.extend(
        [
            BASE_DIR / "data" / "household_electricity_consumption.csv",
            BASE_DIR.parent
            / "Technical Project"
            / "household_electricity_consumption.csv",
            BASE_DIR.parent
            / "Technical Project"
            / "Technical Project"
            / "household_electricity_consumption.csv",
        ]
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return None
