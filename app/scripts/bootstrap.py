import argparse
import json
from pathlib import Path

from sqlalchemy import func, select

from app.config import get_settings
from app.database import SessionLocal, engine
from app.models import EnergyReading
from app.scripts.init_db import (
    database_has_schema,
    initialize_database,
    sqlite_database_path,
)
from app.scripts.paths import find_default_dataset
from app.services.demo import seed_demo
from app.services.imports import import_csv_file


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(
        description="Initialize schema, import CSV, seed demo users."
    )
    parser.add_argument("--csv", type=Path, default=None)
    parser.add_argument("--reset", action="store_true")
    parser.add_argument(
        "--skip-import", action="store_true", help="Do not import the CSV."
    )
    args = parser.parse_args()

    db_path = sqlite_database_path()
    if not database_has_schema(db_path) or args.reset:
        initialize_database(reset=args.reset)

    db = SessionLocal()
    summary: dict = {"database": str(db_path)}
    try:
        reading_count = int(
            db.scalar(select(func.count(EnergyReading.id))) or 0
        )
        if not args.skip_import and (args.reset or not reading_count):
            csv_path = args.csv or find_default_dataset()
            if csv_path is None:
                raise SystemExit(
                    "Dataset not found. Pass --csv or set DATASET_PATH."
                )
            import_result = import_csv_file(db, csv_path)
            db.commit()
            summary["import"] = import_result
        else:
            summary["import"] = {"skipped": True, "reading_count": reading_count}

        summary["seed"] = seed_demo(db)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    linear_dir = Path(settings.linear_model_dir)
    summary["model"] = {
        "runtime": str(linear_dir),
        "ready": (linear_dir / "stage1_linear.joblib").exists()
        and (linear_dir / "stage2_linear.joblib").exists(),
    }

    engine.dispose()
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
