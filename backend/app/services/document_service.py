import os
import uuid
from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models.document import Document, DocumentStatus, File

ALLOWED_MIME = {"application/pdf", "image/jpeg", "image/png", "image/tiff"}


async def save_upload(file: UploadFile, db: AsyncSession, user_id: int) -> Document:
    # Проверка MIME
    if file.content_type not in ALLOWED_MIME:
        raise HTTPException(status_code=400, detail=f"Неподдерживаемый тип файла: {file.content_type}")

    content = await file.read()
    size = len(content)

    if size > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Файл слишком большой")

    # Дополнительная проверка магических байт
    _validate_magic_bytes(content, file.content_type)

    # Сохраняем файл
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    stored_name = f"{uuid.uuid4()}_{file.filename}"
    file_path = os.path.join(settings.UPLOAD_DIR, stored_name)
    with open(file_path, "wb") as f:
        f.write(content)

    db_file = File(
        original_name=file.filename,
        stored_name=stored_name,
        file_path=file_path,
        file_size=size,
        mime_type=file.content_type,
    )
    db.add(db_file)
    await db.flush()

    doc = Document(user_id=user_id, file_id=db_file.id)
    db.add(doc)
    await db.flush()
    return doc


def _validate_magic_bytes(content: bytes, mime_type: str):
    """Проверяет первые байты файла чтобы нельзя было подделать MIME."""
    magic_map = {
        "application/pdf": b"%PDF",
        "image/jpeg": b"\xff\xd8\xff",
        "image/png": b"\x89PNG",
        "image/tiff": (b"II*\x00", b"MM\x00*"),
    }
    expected = magic_map.get(mime_type)
    if not expected:
        return
    if isinstance(expected, tuple):
        if not any(content.startswith(e) for e in expected):
            raise HTTPException(status_code=400, detail="Содержимое файла не совпадает с MIME типом")
    else:
        if not content.startswith(expected):
            raise HTTPException(status_code=400, detail="Содержимое файла не совпадает с MIME типом")


async def get_document(doc_id: int, user_id: int, db: AsyncSession) -> Document:
    result = await db.execute(
        select(Document)
        .where(Document.id == doc_id, Document.user_id == user_id)
        .options(selectinload(Document.file))
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Документ не найден")
    return doc


async def get_document_results(doc_id: int, user_id: int, db: AsyncSession) -> Document:
    result = await db.execute(
        select(Document)
        .where(Document.id == doc_id, Document.user_id == user_id)
        .options(
            selectinload(Document.processed_text),
            selectinload(Document.themes).selectinload("segments"),
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Документ не найден")
    return doc


async def get_user_documents(user_id: int, db: AsyncSession, skip: int = 0, limit: int = 50):
    result = await db.execute(
        select(Document)
        .where(Document.user_id == user_id)
        .order_by(Document.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


async def delete_document(doc_id: int, user_id: int, db: AsyncSession):
    doc = await get_document(doc_id, user_id, db)
    if doc.status == DocumentStatus.PROCESSING:
        raise HTTPException(status_code=409, detail="Нельзя удалить документ в процессе обработки")
    # Удаляем физический файл
    if doc.file and os.path.exists(doc.file.file_path):
        try:
            os.remove(doc.file.file_path)
        except OSError:
            pass
    # Каскадное удаление через ORM (cascade настроен в моделях)
    await db.delete(doc.file)
    await db.flush()
