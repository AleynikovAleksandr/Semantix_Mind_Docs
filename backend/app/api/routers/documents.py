from fastapi import APIRouter, Depends, UploadFile, File, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.dependencies import require_auth, require_write, require_delete
from app.models.user import User
from app.schemas.document import (
    DocumentUploadResponse, DocumentStatusResponse,
    DocumentListItem, DocumentResultResponse,
)
from app.services.document_service import (
    save_upload, get_document, get_document_results,
    get_user_documents, delete_document,
)

router = APIRouter()


@router.post("/upload", response_model=DocumentUploadResponse, status_code=202,
             summary="Загрузить документ (PDF/JPG/PNG/TIFF)")
async def upload(
    file: UploadFile = File(...),
    user: User = Depends(require_write),
    db: AsyncSession = Depends(get_db),
):
    doc = await save_upload(file, db, user.id)

    # Запускаем Celery pipeline
    from worker.orchestrator import process_document
    task = process_document.delay(doc.id)
    doc.celery_task_id = task.id
    await db.flush()

    return DocumentUploadResponse(
        document_id=doc.id,
        file_name=file.filename,
        status=doc.status,
        celery_task_id=task.id,
        message="Документ принят, обработка запущена",
    )


@router.get("/", response_model=list[DocumentListItem],
            summary="Список документов текущего пользователя")
async def list_docs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    return await get_user_documents(user.id, db, skip=skip, limit=limit)


@router.get("/{doc_id}/status", response_model=DocumentStatusResponse,
            summary="Статус обработки документа")
async def doc_status(
    doc_id: int,
    user: User = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    doc = await get_document(doc_id, user.id, db)
    return DocumentStatusResponse(
        document_id=doc.id,
        status=doc.status,
        page_count=doc.page_count,
        processing_time=doc.processing_time,
        error_message=doc.error_message,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


@router.get("/{doc_id}/results", response_model=DocumentResultResponse,
            summary="Полные результаты обработки (текст + темы)")
async def doc_results(
    doc_id: int,
    user: User = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    from fastapi import HTTPException
    from app.models.document import DocumentStatus
    doc = await get_document_results(doc_id, user.id, db)
    if doc.status != DocumentStatus.PROCESSED:
        raise HTTPException(
            status_code=400,
            detail=f"Документ ещё не обработан. Статус: {doc.status}"
        )
    pt = doc.processed_text
    return DocumentResultResponse(
        document_id=doc.id,
        status=doc.status,
        raw_text=pt.raw_text if pt else None,
        cleaned_text=pt.cleaned_text if pt else None,
        ocr_confidence=pt.ocr_confidence if pt else None,
        themes=doc.themes,
    )


@router.delete("/{doc_id}", status_code=204,
               summary="Удалить документ и все связанные данные")
async def delete_doc(
    doc_id: int,
    user: User = Depends(require_delete),
    db: AsyncSession = Depends(get_db),
):
    await delete_document(doc_id, user.id, db)
