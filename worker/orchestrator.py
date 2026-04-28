"""
Celery pipeline: OCR → очистка → NLP → сохранение + индексы поиска.
"""

import json
import time
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker, joinedload

from app.config import settings
from app.core.celery_logging import CeleryLogger
from worker.celery_app import celery_app

# Синхронный движок для Celery (psycopg2, не asyncpg)
_sync_engine = create_engine(
    settings.sync_database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    pool_recycle=3600,
)
_SyncSession = sessionmaker(bind=_sync_engine)

_logger = CeleryLogger()


def _embed_text_for_search(text_value: str) -> str | None:
    if not text_value or not text_value.strip():
        return None

    from worker.nlp_analyzer import _load_model

    model = _load_model()
    if model in (None, "fallback"):
        return None

    vector = model.encode([text_value], show_progress_bar=False)[0].tolist()
    return "[" + ",".join(f"{v:.8f}" for v in vector) + "]"


def _upsert_search_index(db, document_id: int, cleaned_text: str, topics: list[dict]):
    # 1) Индекс всего документа (full-text)
    db.execute(
        text(
            """
            INSERT INTO document_search_index(document_id, search_vector)
            VALUES (:document_id, to_tsvector('russian', :content))
            ON CONFLICT (document_id) DO UPDATE
            SET search_vector = EXCLUDED.search_vector
            """
        ),
        {"document_id": document_id, "content": cleaned_text or ""},
    )

    # 2) Индекс тем (full-text + embedding)
    for theme_index, topic in enumerate(topics):
        keywords_raw = topic.get("keywords")
        try:
            keywords = json.loads(keywords_raw) if keywords_raw else []
            if not isinstance(keywords, list):
                keywords = []
        except Exception:
            keywords = []

        segments = topic.get("segments") or []
        combined_text = " ".join(
            [topic.get("label", ""), " ".join(keywords), " ".join(segments)]
        ).strip()
        embedding_literal = _embed_text_for_search(combined_text)

        db.execute(
            text(
                """
                INSERT INTO topic_search_index (
                    document_id,
                    theme_index,
                    search_vector,
                    keywords,
                    embedding
                )
                VALUES (
                    :document_id,
                    :theme_index,
                    to_tsvector('russian', :combined_text),
                    :keywords,
                    CAST(:embedding AS vector)
                )
                ON CONFLICT (document_id, theme_index) DO UPDATE
                SET search_vector = EXCLUDED.search_vector,
                    keywords = EXCLUDED.keywords,
                    embedding = EXCLUDED.embedding
                """
            ),
            {
                "document_id": document_id,
                "theme_index": theme_index,
                "combined_text": combined_text,
                "keywords": keywords,
                "embedding": embedding_literal,
            },
        )


def _run_pipeline(document_id: int, db):
    """Весь пайплайн внутри одной сессии/транзакции."""
    from app.models.document import Document, DocumentStatus
    from app.models.processed_text import ProcessedText
    from app.models.theme import DocumentTheme, TopicSegment
    from worker.ocr_processor import process_file
    from worker.text_cleaner import clean_text
    from worker.nlp_analyzer import analyze_topics

    doc = db.execute(
        select(Document)
        .where(Document.id == document_id)
        .options(joinedload(Document.file))
    ).unique().scalar_one_or_none()

    if not doc:
        _logger.error("document_not_found", document_id=document_id)
        return

    start_time = time.time()

    doc.status = DocumentStatus.PROCESSING
    db.flush()
    db.commit()

    try:
        _logger.info("ocr_started", document_id=document_id, file_path=doc.file.file_path)
        raw_text, ocr_confidence, page_count = process_file(
            doc.file.file_path, doc.file.mime_type
        )
        doc.page_count = page_count

        _logger.info("text_clean_started", document_id=document_id)
        cleaned_text = clean_text(raw_text)

        # Вставка/обновление processed_text в БД
        existing_processed = db.execute(
            select(ProcessedText).where(ProcessedText.document_id == doc.id)
        ).scalar_one_or_none()

        if existing_processed:
            existing_processed.raw_text = raw_text
            existing_processed.cleaned_text = cleaned_text
            existing_processed.ocr_confidence = ocr_confidence
            processed_id = existing_processed.id
        else:
            processed = ProcessedText(
                document_id=doc.id,
                raw_text=raw_text,
                cleaned_text=cleaned_text,
                ocr_confidence=ocr_confidence,
            )
            db.add(processed)
            db.flush()
            processed_id = processed.id

        _logger.info(
            "processed_text_saved",
            document_id=document_id,
            processed_text_id=processed_id,
            page_count=page_count,
            ocr_confidence=ocr_confidence,
        )

        _logger.info("nlp_started", document_id=document_id)
        topics = analyze_topics(cleaned_text)

        # очищаем старые темы, чтобы не копились дубликаты
        doc.themes.clear()
        db.flush()

        for order, topic in enumerate(topics):
            theme = DocumentTheme(
                document_id=doc.id,
                theme_label=topic["label"],
                keywords=topic.get("keywords"),
                order=order,
                confidence=topic.get("confidence"),
            )
            db.add(theme)
            db.flush()

            for seg_order, seg_text in enumerate(topic.get("segments", [])):
                db.add(TopicSegment(
                    theme_id=theme.id,
                    segment_text=seg_text,
                    order=seg_order,
                ))

        _upsert_search_index(db, doc.id, cleaned_text, topics)

        elapsed = time.time() - start_time
        doc.processing_time = round(elapsed, 2)
        doc.status = DocumentStatus.PROCESSED

        if elapsed > 120:
            _logger.warning("slow_task_alert", document_id=document_id, duration_seconds=round(elapsed, 2))
        if ocr_confidence is not None and ocr_confidence < 60:
            _logger.warning("low_ocr_confidence_alert", document_id=document_id, ocr_confidence=ocr_confidence)

        db.commit()
        _logger.info("pipeline_finished", document_id=document_id, duration_seconds=round(elapsed, 2))

    except Exception as exc:
        db.rollback()
        doc.status = DocumentStatus.ERROR
        doc.error_message = str(exc)[:2000]
        db.commit()
        _logger.exception("pipeline_failed", document_id=document_id, error=str(exc))
        raise


@celery_app.task(bind=True, max_retries=3, default_retry_delay=15)
@CeleryLogger.log_task()
def process_document(self, document_id: int):
    """
    Celery задача с deadlock retry.
    """
    max_db_retries = 2

    for attempt in range(max_db_retries):
        with _SyncSession() as db:
            try:
                _run_pipeline(document_id, db)
                return

            except OperationalError as e:
                db.rollback()
                if "deadlock" in str(e).lower() and attempt < max_db_retries - 1:
                    wait = 0.5 * (2 ** attempt)
                    _logger.warning(
                        "deadlock_retry",
                        document_id=document_id,
                        attempt=attempt + 1,
                        wait_seconds=wait,
                    )
                    time.sleep(wait)
                    continue

                _logger.error("db_error", document_id=document_id, error=str(e))
                raise self.retry(exc=e)

            except Exception as exc:
                _logger.error("pipeline_retry", document_id=document_id, error=str(exc))
                raise self.retry(exc=exc)
