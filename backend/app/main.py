import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.config import settings
from app.database import engine, Base
from app.api.routers import auth, documents, export
from app.utils.logging_middleware import RequestLoggingMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Запуск {settings.APP_NAME}...")
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    # Создаём таблицы если не существуют (только для dev; в prod — alembic)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("БД инициализирована.")
    yield
    logger.info("Завершение работы...")
    await engine.dispose()


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


@app.get("/health", tags=["System"], summary="Health check")
async def health():
    return {"status": "ok", "app": settings.APP_NAME}
