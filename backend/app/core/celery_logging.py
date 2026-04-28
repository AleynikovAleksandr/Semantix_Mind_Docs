import json
import logging
import os
import sys
import time
from contextvars import ContextVar
from functools import wraps
from typing import Optional


class CeleryLogger:
    _request_id_ctx: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
    _initialized = False

    def __init__(self, level: str = "INFO"):
        self.logger = logging.getLogger("celery_worker")

        if not CeleryLogger._initialized:
            self.logger.setLevel(level)
            self._setup_handler()
            CeleryLogger._initialized = True

    def _setup_handler(self):
        os.makedirs("core/logging", exist_ok=True)

        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(self._JSONFormatter())

        file_handler = logging.FileHandler("core/logging/celery_logging.log", encoding="utf-8")
        file_handler.setFormatter(self._JSONFormatter())

        self.logger.handlers.clear()
        self.logger.addHandler(stream_handler)
        self.logger.addHandler(file_handler)
        self.logger.propagate = False

        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    @classmethod
    def set_task_id(cls, task_id: str):
        cls._request_id_ctx.set(task_id)

    @classmethod
    def get_task_id(cls) -> Optional[str]:
        return cls._request_id_ctx.get()

    class _JSONFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            log_record = {
                "timestamp": int(time.time() * 1000),
                "level": record.levelname,
                "message": record.getMessage(),
                "logger": record.name,
                "module": record.module,
                "function": record.funcName,
                "line": record.lineno,
                "task_id": CeleryLogger.get_task_id(),
            }

            if hasattr(record, "extra_data"):
                log_record.update(record.extra_data)

            if record.exc_info:
                log_record["exception"] = self.formatException(record.exc_info)

            return json.dumps(log_record, ensure_ascii=False)

    def info(self, message: str, **kwargs):
        self.logger.info(message, extra={"extra_data": kwargs} if kwargs else None)

    def warning(self, message: str, **kwargs):
        self.logger.warning(message, extra={"extra_data": kwargs} if kwargs else None)

    def error(self, message: str, **kwargs):
        self.logger.error(message, extra={"extra_data": kwargs} if kwargs else None)

    def exception(self, message: str, **kwargs):
        self.logger.exception(message, extra={"extra_data": kwargs} if kwargs else None)

    @classmethod
    def log_task(cls):
        def decorator(func):
            @wraps(func)
            def wrapper(self, *args, **kwargs):
                logger = cls()

                task_id = getattr(self.request, "id", None)
                cls.set_task_id(task_id)

                start_time = time.time()

                logger.info(
                    "task_started",
                    task_name=func.__name__,
                    task_id=task_id,
                )

                try:
                    result = func(self, *args, **kwargs)

                    duration = int((time.time() - start_time) * 1000)

                    logger.info(
                        "task_finished",
                        task_name=func.__name__,
                        duration_ms=duration,
                    )

                    return result

                except Exception as e:
                    duration = int((time.time() - start_time) * 1000)

                    logger.exception(
                        "task_failed",
                        task_name=func.__name__,
                        duration_ms=duration,
                        retries=getattr(self.request, "retries", 0),
                        error=str(e),
                    )

                    raise

            return wrapper

        return decorator
