from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    app_name: str = "Home Energy Consumption API"
    api_prefix: str = "/api/v1"
    database_url: str = f"sqlite:///{BASE_DIR / 'app.db'}"
    jwt_secret: str = "dev-only-change-this-secret-32-bytes-min"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    model_version: str = "linear-v1"
    linear_model_dir: str = str(BASE_DIR / "models" / "linear-v1")

    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
