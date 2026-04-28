from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_auth
from app.database import get_db
from app.models.user import User
from app.schemas.search import TextSearchResult, SemanticSearchResult
from app.services.search_service import text_search, semantic_search

router = APIRouter()


@router.get("/text", response_model=list[TextSearchResult], summary="Полнотекстовый поиск")
async def search_text(
    q: str = Query(..., min_length=2),
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    return await text_search(q=q, user_id=user.id, db=db, limit=limit)


@router.get("/semantic", response_model=list[SemanticSearchResult], summary="Семантический поиск")
async def search_semantic(
    q: str = Query(..., min_length=2),
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    return await semantic_search(q=q, user_id=user.id, db=db, limit=limit)
