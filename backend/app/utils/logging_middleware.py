import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import AsyncSessionLocal
from app.models.request_log import RequestLog
from loguru import logger


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.monotonic()
        response = await call_next(request)
        elapsed_ms = (time.monotonic() - start) * 1000

        # Не логируем health check и docs
        if request.url.path in ("/health", "/docs", "/openapi.json", "/redoc"):
            return response

        try:
            async with AsyncSessionLocal() as db:
                log = RequestLog(
                    endpoint=str(request.url.path),
                    method=request.method,
                    status_code=response.status_code,
                    response_time_ms=round(elapsed_ms, 2),
                    ip_address=request.client.host if request.client else None,
                )
                db.add(log)
                await db.commit()
        except Exception as e:
            logger.warning(f"Logging middleware error: {e}")

        return response
