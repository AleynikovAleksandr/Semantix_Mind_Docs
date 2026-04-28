from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.schemas.auth import (
    UserRegister, Token, RefreshTokenRequest,
    UserOut, APIKeyCreate, APIKeyOut, APIKeyCreated,
)
from app.services.auth_service import (
    register_user, authenticate_user,
    create_access_token, create_refresh_token,
    do_refresh, create_api_key,
)
from app.api.dependencies import require_auth
from app.models.user import User
from app.models.api_key import APIKey

router = APIRouter()


# ── Регистрация / Логин / Refresh ─────────────────────────────────────────────

@router.post("/register", response_model=UserOut, status_code=201,
             summary="Регистрация нового пользователя")
async def register(body: UserRegister, db: AsyncSession = Depends(get_db)):
    user = await register_user(body.email, body.password, db, body.full_name)
    return user


@router.post("/login", response_model=Token,
             summary="Логин (email + password) → JWT токены")
async def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    user = await authenticate_user(form.username, form.password, db)
    return Token(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/refresh", response_model=Token,
             summary="Обновить access token через refresh token")
async def refresh(body: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    access, refresh = await do_refresh(body.refresh_token, db)
    return Token(access_token=access, refresh_token=refresh)


@router.post("/logout", summary="Логаут (клиент должен удалить токены)")
async def logout(user: User = Depends(require_auth)):
    return {"message": "Выход выполнен"}


@router.get("/me", response_model=UserOut, summary="Информация о текущем пользователе")
async def me(user: User = Depends(require_auth)):
    return user


# ── API Keys ──────────────────────────────────────────────────────────────────

@router.post("/api-keys", response_model=APIKeyCreated, status_code=201,
             summary="Создать API ключ (ключ показывается только один раз!)")
async def create_key(
    body: APIKeyCreate,
    user: User = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    api_key, raw = await create_api_key(
        user.id, body.name, db,
        expires_days=body.expires_days,
        permissions=body.permissions,
    )
    return APIKeyCreated(
        id=api_key.id,
        name=api_key.name,
        key=raw,
        key_prefix=api_key.key_prefix,
        permissions=api_key.permissions,
        expires_at=api_key.expires_at,
        last_used_at=api_key.last_used_at,
        is_active=api_key.is_active,
        created_at=api_key.created_at,
    )


@router.get("/api-keys", response_model=list[APIKeyOut],
            summary="Список API ключей текущего пользователя")
async def list_keys(
    user: User = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(APIKey).where(APIKey.user_id == user.id))
    return result.scalars().all()


@router.delete("/api-keys/{key_id}", status_code=204,
               summary="Удалить API ключ")
async def delete_key(
    key_id: int,
    user: User = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    from fastapi import HTTPException
    result = await db.execute(
        select(APIKey).where(APIKey.id == key_id, APIKey.user_id == user.id)
    )
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(status_code=404, detail="API ключ не найден")
    await db.delete(key)
