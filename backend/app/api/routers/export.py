from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import PlainTextResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.dependencies import require_auth
from app.models.user import User
from app.models.document import DocumentStatus
from app.services.document_service import get_document_results
from app.services.export_service import export_txt, export_json, export_csv

router = APIRouter()


async def _get_processed_doc(doc_id: int, user: User, db: AsyncSession):
    doc = await get_document_results(doc_id, user.id, db)
    if doc.status != DocumentStatus.PROCESSED:
        raise HTTPException(
            status_code=400,
            detail=f"Документ ещё не обработан. Статус: {doc.status}"
        )
    return doc


@router.get("/{doc_id}/txt", response_class=PlainTextResponse,
            summary="Экспорт результатов в TXT")
async def export_as_txt(
    doc_id: int,
    user: User = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    doc = await _get_processed_doc(doc_id, user, db)
    return PlainTextResponse(
        content=export_txt(doc),
        headers={"Content-Disposition": f'attachment; filename="document_{doc_id}.txt"'},
    )


@router.get("/{doc_id}/json",
            summary="Экспорт результатов в JSON")
async def export_as_json(
    doc_id: int,
    user: User = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    doc = await _get_processed_doc(doc_id, user, db)
    return JSONResponse(
        content=export_json(doc),
        headers={"Content-Disposition": f'attachment; filename="document_{doc_id}.json"'},
    )


@router.get("/{doc_id}/csv", response_class=PlainTextResponse,
            summary="Экспорт тем и сегментов в CSV")
async def export_as_csv(
    doc_id: int,
    user: User = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    doc = await _get_processed_doc(doc_id, user, db)
    return PlainTextResponse(
        content=export_csv(doc),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="document_{doc_id}.csv"'},
    )
