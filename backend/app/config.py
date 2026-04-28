from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    APP_NAME: str = "Document Processing System"
    DEBUG: bool = False
    UPLOAD_DIR: str = "/app/uploads"
    MAX_FILE_SIZE_MB: int = 50

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://docuser:docpassword@db:5432/docprocessing"

    # Redis / Celery
    REDIS_URL: str = "redis://redis:6379/0"
    CELERY_BROKER_URL: str = "redis://redis:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/1"

    # JWT
    JWT_SECRET_KEY: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Tesseract
    TESSERACT_CMD: str = "/usr/bin/tesseract"
    TESSERACT_LANG: str = "rus+eng"

    # NLP
    EMBEDDING_MODEL: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    HF_HOME: str = "/root/.cache/huggingface"

    @property
    def sync_database_url(self) -> str:
        """Синхронный URL для Celery (psycopg2)."""
        url = self.DATABASE_URL
        # postgresql+asyncpg:// → postgresql://
        url = url.replace("postgresql+asyncpg://", "postgresql://")
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
