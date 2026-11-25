import argparse
import sqlite3
from pathlib import Path

from sqlalchemy.engine import make_url

from app.config import BASE_DIR, get_settings

SCHEMA_FILES = [BASE_DIR / "db" / "01_business.sql"]


def sqlite_database_path() -> Path:
    settings = get_settings()
    url = make_url(settings.database_url)
    if not url.drivername.startswith("sqlite"):
        raise SystemExit("init_db only supports SQLite databases.")
    if not url.database:
        raise SystemExit("DATABASE_URL does not point to a database file.")
    return Path(url.database).expanduser().resolve()


def database_has_schema(path: Path) -> bool:
    if not path.exists():
        return False
    with sqlite3.connect(path) as connection:
        rows = connection.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name = 'users'"
        ).fetchall()
    return bool(rows)


def initialize_database(*, reset: bool = False, quiet: bool = False) -> Path:
    path = sqlite_database_path()
    if path.exists() and database_has_schema(path):
        if not reset:
            raise SystemExit(
                f"Database already initialized at {path}. Use --reset to rebuild."
            )
        for suffix in ("", "-wal", "-shm"):
            candidate = Path(f"{path}{suffix}")
            if candidate.exists():
                candidate.unlink()
    elif reset and path.exists():
        path.unlink()

    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        for schema_file in SCHEMA_FILES:
            connection.executescript(schema_file.read_text(encoding="utf-8"))
        connection.commit()

    if not quiet:
        print(f"Initialized database: {path}")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize the SQLite schema.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete an existing database and recreate the schema.",
    )
    args = parser.parse_args()
    initialize_database(reset=args.reset)


if __name__ == "__main__":
    main()
