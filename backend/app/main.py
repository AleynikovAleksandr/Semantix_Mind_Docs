import os
from contextlib import asynccontextmanager
import importlib.util
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.config import settings
from app.api.routers import auth, documents, export, search
from app.utils.logging_middleware import RequestLoggingMiddleware


def _database_init_script_path() -> Path | None:
    """Find database/initial_data.py both in repo layout and Docker /app layout."""
    current_file = Path(__file__).resolve()
    candidates = [
        current_file.parents[2] / "database" / "initial_data.py",
        current_file.parents[1] / "database" / "initial_data.py",
        Path.cwd() / "database" / "initial_data.py",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _initialize_database_if_needed():
    """Инициализирует БД и применяет database/schema.sql при старте приложения."""
    script_path = _database_init_script_path()
    if script_path is None:
        logger.warning("DB init helper not found in repo or Docker paths")
        return

    spec = importlib.util.spec_from_file_location("database.initial_data", script_path)
    if spec is None or spec.loader is None:
        logger.warning("Unable to load database/initial_data.py")
        return

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    initializer = module.DBInitializer()
    initializer.initialize()
    logger.info("Database schema initialized")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Запуск {settings.APP_NAME}...")
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    _initialize_database_if_needed()

    yield


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="""
## Document Processing System API

Система автоматической обработки документов:
- **OCR** — распознавание текста из PDF/изображений (Tesseract + OpenCV)
- **Очистка** — нормализация и очистка OCR-текста
- **NLP** — тематическое моделирование (sentence-transformers + KMeans)
- **Экспорт** — TXT / JSON / CSV

### Аутентификация
Поддерживаются два метода:
1. `Authorization: Bearer <JWT>` — после логина
2. `X-API-Key: <key>` — API ключ (создаётся в /api/auth/api-keys)
    """,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)

# Routers
app.include_router(auth.router,      prefix="/api/auth",      tags=["Auth"])
app.include_router(documents.router, prefix="/api/documents", tags=["Documents"])
app.include_router(export.router,    prefix="/api/export",    tags=["Export"])
app.include_router(search.router,    prefix="/api/search",    tags=["Search"])


@app.get("/health", tags=["System"], summary="Health check")
async def health():
    return {"status": "ok", "app": settings.APP_NAME}
