from app.database import SessionLocal
from app.services.demo import seed_demo


def main() -> None:
    db = SessionLocal()
    try:
        result = seed_demo(db)
        print(result)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
