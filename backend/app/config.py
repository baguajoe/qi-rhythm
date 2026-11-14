"""Application configuration, loaded from environment variables."""

import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR.parent / ".env")
load_dotenv(BASE_DIR / ".env")


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).lower() in {"1", "true", "yes", "on"}


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-insecure-change-me")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-insecure-jwt-change-me")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=int(os.getenv("JWT_ACCESS_HOURS", "12")))
    DISPLAY_TOKEN_MINUTES = int(os.getenv("DISPLAY_TOKEN_MINUTES", "15"))

    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", "postgresql+psycopg://qi:qi@localhost:5432/qi_rhythm"
    ).replace("postgres://", "postgresql+psycopg://", 1)
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")

    # Storage: "local" (dev) or "r2" (Cloudflare R2, S3-compatible)
    STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local")
    LOCAL_STORAGE_DIR = os.getenv("LOCAL_STORAGE_DIR", str(BASE_DIR / "instance" / "recordings"))
    R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID", "")
    R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID", "")
    R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY", "")
    R2_BUCKET = os.getenv("R2_BUCKET", "qi-rhythm-recordings")
    MAX_CONTENT_LENGTH = 25 * 1024 * 1024  # 25 MB upload cap

    DEFAULT_RECORDING_RETENTION_DAYS = int(os.getenv("RECORDING_RETENTION_DAYS", "7"))

    # Scoring weights (must sum to 100)
    SCORE_WEIGHTS = {"pattern": 40, "timing": 30, "tempo": 15, "completion": 15}

    SOCKETIO_ASYNC_MODE = os.getenv("SOCKETIO_ASYNC_MODE", "threading")


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "TEST_DATABASE_URL", "postgresql+psycopg://qi:qi@localhost:5432/qi_rhythm_test"
    )
    JWT_SECRET_KEY = "test-jwt-secret-key-that-is-long-enough-32b"
    STORAGE_BACKEND = "local"


config_by_name = {"default": Config, "test": TestConfig}
