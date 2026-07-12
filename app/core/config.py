from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    PROJECT_NAME: str = "TruckGrad"
    SITE_URL: str = "https://truckgrad.ru"
    VERSION: str = "1.0.0"
    API_PREFIX: str = "/api/v1"

    # Runtime mode
    ENV: str = "dev"
    LOG_LEVEL: str = "INFO"

    # Database (SQLite by default for local development)
    DATABASE_URL: str = "sqlite+aiosqlite:///./truckgrad.db"

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # JWT
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Elasticsearch
    ELASTICSEARCH_URL: str = "http://localhost:9200"

    # Integrations provider mode
    PROVIDER_MODE: str = "mock"

    # Laximo VIN decoder
    LAXIMO_API_URL: str = "https://ws.laximo.ru"
    LAXIMO_USER: str = ""
    LAXIMO_PASSWORD: str = ""

    # CDEK delivery
    CDEK_ACCOUNT: str = ""
    CDEK_SECURE_PASSWORD: str = ""
    CDEK_TOKEN: str = ""
    CDEK_API_URL: str = "https://api.cdek.ru/v2"

    # ПЭК delivery
    PEC_API_KEY: str = ""
    PEC_API_URL: str = "https://pecom.ru/api"

    # Деловые Линии delivery
    DL_API_KEY: str = ""
    DL_API_URL: str = "https://www.dellin.ru/api"

    # Notifications providers keys/endpoints
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMS_API_URL: str = ""
    SMS_API_KEY: str = ""
    TELEGRAM_BOT_TOKEN: str = ""

    # S3 Storage
    S3_BUCKET: str = ""
    S3_ENDPOINT: str = ""
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_REGION: str = "ru-1"

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
