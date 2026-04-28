from functools import partial
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.services.auth_service import get_current_user


async def require_auth(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Зависимость: любая аутентификация (JWT или API Key), право read."""
    return await get_current_user(request, db, permission="read")


async def require_write(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Зависимость: требует право write."""
    return await get_current_user(request, db, permission="write")


async def require_delete(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Зависимость: требует право delete."""
    return await get_current_user(request, db, permission="delete")
