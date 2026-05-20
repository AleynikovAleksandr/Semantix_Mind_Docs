from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    APP_NAME: str = Field(...)
    DEBUG: bool = Field(...)
    UPLOAD_DIR: str = Field(...)
    MAX_FILE_SIZE_MB: int = Field(...)

    # Database
    DATABASE_URL: str = Field(...)

    # Redis / Celery
    REDIS_URL: str = Field(...)
    CELERY_BROKER_URL: str = Field(...)
    CELERY_RESULT_BACKEND: str = Field(...)

    # JWT
    JWT_SECRET_KEY: str = Field(...)
    JWT_ALGORITHM: str = Field(...)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(...)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(...)

    # Tesseract
    TESSERACT_CMD: str = Field(...)
    TESSERACT_LANG: str = Field(...)

    # NLP
    EMBEDDING_MODEL: str = Field(...)
    HF_HOME: str = Field(...)

    @property
    def sync_database_url(self) -> str:
        """Синхронный URL для Celery (psycopg2)."""
        return self.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
