from functools import lru_cache

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings


@lru_cache(maxsize=1)
def _load_embedding_model():
    """Ленивая загрузка модели только для semantic endpoint."""
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(settings.EMBEDDING_MODEL)


def _to_pgvector_literal(values: list[float]) -> str:
    return "[" + ",".join(f"{v:.8f}" for v in values) + "]"


async def text_search(q: str, user_id: int, db: AsyncSession, limit: int = 20):
    stmt = text(
        """
        SELECT dsi.document_id,
               ts_rank(dsi.search_vector, plainto_tsquery('russian', :q)) AS rank
        FROM document_search_index dsi
        JOIN documents d ON d.id = dsi.document_id
        WHERE d.user_id = :user_id
          AND dsi.search_vector @@ plainto_tsquery('russian', :q)
        ORDER BY rank DESC
        LIMIT :limit
        """
    )
    rows = (await db.execute(stmt, {"q": q, "user_id": user_id, "limit": limit})).mappings().all()
    return [{"document_id": int(r["document_id"]), "rank": float(r["rank"])} for r in rows]


async def semantic_search(q: str, user_id: int, db: AsyncSession, limit: int = 20):
    try:
        model = _load_embedding_model()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Не удалось загрузить embedding-модель: {exc}")

    embedding = model.encode([q], show_progress_bar=False)[0].tolist()
    vector_literal = _to_pgvector_literal(embedding)

    stmt = text(
        """
        SELECT tsi.document_id,
               tsi.theme_index,
               (tsi.embedding <=> CAST(:embedding AS vector)) AS distance
        FROM topic_search_index tsi
        JOIN documents d ON d.id = tsi.document_id
        WHERE d.user_id = :user_id
          AND tsi.embedding IS NOT NULL
        ORDER BY tsi.embedding <=> CAST(:embedding AS vector)
        LIMIT :limit
        """
    )

    rows = (
        await db.execute(
            stmt,
            {"embedding": vector_literal, "user_id": user_id, "limit": limit},
        )
    ).mappings().all()
    return [
        {
            "document_id": int(r["document_id"]),
            "theme_index": int(r["theme_index"]),
            "distance": float(r["distance"]),
        }
        for r in rows
    ]
