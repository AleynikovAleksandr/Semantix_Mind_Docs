import os
from pydantic import BaseSettings, Field

BASE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../..")
)


class Settings(BaseSettings):
    EMBEDDING_MODEL: str = Field(...)
    TESSERACT_CMD: str = Field(...)

    class Config:
        env_file = os.path.join(BASE_DIR, ".env")


settings = Settings()
