"""
Celery pipeline: OCR → очистка → NLP → сохранение.

Ключевые исправления из code review:
  1. Синхронный движок через psycopg2 (не asyncpg)
  2. ОДНА транзакция — один commit в конце
  3. joinedload вместо selectinload для синхронного кода
  4. Deadlock retry с exponential backoff
  5. Пул соединений настроен
  6. Таймауты через Celery soft_time_limit
"""

import time
from loguru import logger
from sqlalchemy import create_engine, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker, joinedload

from worker.celery_app import celery_app
from app.config import settings

# Синхронный движок для Celery (psycopg2, не asyncpg)
_sync_engine = create_engine(
    settings.sync_database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    pool_recycle=3600,
)
_SyncSession = sessionmaker(bind=_sync_engine)


def _run_pipeline(document_id: int, db):
    """Весь пайплайн внутри одной сессии/транзакции."""
    from app.models.document import Document, DocumentStatus
    from app.models.processed_text import ProcessedText
    from app.models.theme import DocumentTheme, TopicSegment
    from worker.ocr_processor import process_file
    from worker.text_cleaner import clean_text
    from worker.nlp_analyzer import analyze_topics

    # ── 1. Загружаем документ ────────────────────────────────────────────────
    doc = db.execute(
        select(Document)
        .where(Document.id == document_id)
        .options(joinedload(Document.file))
    ).unique().scalar_one_or_none()

    if not doc:
        logger.error(f"[{document_id}] Документ не найден")
        return

    start_time = time.time()

    # ── 2. Статус → processing (сразу видно в API) ───────────────────────────
    doc.status = DocumentStatus.PROCESSING
    db.flush()
    db.commit()  # маленький промежуточный commit только для статуса

    try:
        # ── 3. OCR ───────────────────────────────────────────────────────────
        logger.info(f"[{document_id}] OCR: {doc.file.file_path}")
        raw_text, ocr_confidence, page_count = process_file(
            doc.file.file_path, doc.file.mime_type
        )
        doc.page_count = page_count

        # ── 4. Очистка текста ────────────────────────────────────────────────
        logger.info(f"[{document_id}] Очистка текста")
        cleaned_text = clean_text(raw_text)

        # ── 5. Сохраняем текст ───────────────────────────────────────────────
        processed = ProcessedText(
            document_id=doc.id,
            raw_text=raw_text,
            cleaned_text=cleaned_text,
            ocr_confidence=ocr_confidence,
        )
        db.add(processed)
        db.flush()  # получаем ID

        # ── 6. NLP-анализ ────────────────────────────────────────────────────
        logger.info(f"[{document_id}] NLP-анализ")
        topics = analyze_topics(cleaned_text)

        for order, topic in enumerate(topics):
            theme = DocumentTheme(
                document_id=doc.id,
                theme_label=topic["label"],
                keywords=topic.get("keywords"),
                order=order,
                confidence=topic.get("confidence"),
            )
            db.add(theme)
            db.flush()  # нужен theme.id для сегментов

            for seg_order, seg_text in enumerate(topic.get("segments", [])):
                db.add(TopicSegment(
                    theme_id=theme.id,
                    segment_text=seg_text,
                    order=seg_order,
                ))

        # ── 7. Завершение — ОДИН финальный commit ────────────────────────────
        elapsed = time.time() - start_time
        doc.processing_time = round(elapsed, 2)
        doc.status = DocumentStatus.PROCESSED
        db.commit()
        logger.info(f"[{document_id}] Готово за {elapsed:.1f}с")

    except Exception as exc:
        db.rollback()
        # Отдельный коммит только для статуса ошибки
        doc.status = DocumentStatus.ERROR
        doc.error_message = str(exc)[:2000]
        db.commit()
        raise


@celery_app.task(bind=True, max_retries=3, default_retry_delay=15)
def process_document(self, document_id: int):
    """
    Celery задача с deadlock retry.
    """
    max_db_retries = 2

    for attempt in range(max_db_retries):
        with _SyncSession() as db:
            try:
                _run_pipeline(document_id, db)
                return  # успех

            except OperationalError as e:
                db.rollback()
                if "deadlock" in str(e).lower() and attempt < max_db_retries - 1:
                    wait = 0.5 * (2 ** attempt)
                    logger.warning(f"[{document_id}] Deadlock, retry {attempt+1}, ждём {wait}с")
                    time.sleep(wait)
                    continue
                # deadlock не исправился или другая ошибка БД
                logger.error(f"[{document_id}] DB error: {e}")
                raise self.retry(exc=e)

            except Exception as exc:
                logger.error(f"[{document_id}] Pipeline error: {exc}")
                raise self.retry(exc=exc)
