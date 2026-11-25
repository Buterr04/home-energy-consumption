import argparse
from pathlib import Path

from app.database import SessionLocal
from app.scripts.paths import find_default_dataset
from app.services.imports import import_csv_file


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import household electricity readings from CSV."
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=None,
        help="Path to household_electricity_consumption.csv.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate the CSV without writing to the database.",
    )
    args = parser.parse_args()

    path = args.path or find_default_dataset()
    if path is None:
        raise SystemExit(
            "Dataset not found. Pass --path or set DATASET_PATH."
        )

    db = SessionLocal()
    try:
        result = import_csv_file(db, path, dry_run=args.dry_run)
        db.commit()
        print(result)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
