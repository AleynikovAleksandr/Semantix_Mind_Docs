from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.api_key import APIKey
from app.models.user import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)


# ── Passwords ─────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── JWT ───────────────────────────────────────────────────────────────────────

def create_access_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(
        {"sub": str(user_id), "type": "access", "exp": expire},
        settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM,
    )


def create_refresh_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    return jwt.encode(
        {"sub": str(user_id), "type": "refresh", "exp": expire},
        settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM,
    )


def _decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Неверный или просроченный токен")


async def do_refresh(refresh_token: str, db: AsyncSession) -> tuple[str, str]:
    payload = _decode_token(refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Неверный тип токена")
    user_id = int(payload["sub"])
    result = await db.execute(select(User).where(User.id == user_id, User.is_active == True))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Пользователь не найден")
    return create_access_token(user.id), create_refresh_token(user.id)


# ── Users ─────────────────────────────────────────────────────────────────────

async def register_user(
    email: str, password: str, db: AsyncSession, full_name: str | None = None
) -> User:
    result = await db.execute(select(User).where(User.email == email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email уже зарегистрирован")
    user = User(email=email, hashed_password=hash_password(password), full_name=full_name)
    db.add(user)
    await db.flush()
    return user


async def authenticate_user(email: str, password: str, db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Неверный email или пароль")
    if not user.is_active:
        raise HTTPException(status_code=401, detail="Аккаунт отключён")
    user.last_login_at = datetime.now(timezone.utc)
    await db.flush()
    return user


# ── API Keys ──────────────────────────────────────────────────────────────────

async def create_api_key(
    user_id: int,
    name: str,
    db: AsyncSession,
    expires_days: int | None = 365,
    permissions: dict | None = None,
) -> tuple[APIKey, str]:
    raw, key_hash, prefix = APIKey.generate()
    expires_at = (
        datetime.now(timezone.utc) + timedelta(days=expires_days) if expires_days else None
    )
    api_key = APIKey(
        user_id=user_id,
        name=name,
        key_hash=key_hash,
        key_prefix=prefix,
        permissions=permissions or {"read": True, "write": True, "delete": False},
        expires_at=expires_at,
    )
    db.add(api_key)
    await db.flush()
    return api_key, raw


async def _auth_via_api_key(raw_key: str, db: AsyncSession, permission: str) -> User | None:
    key_hash = APIKey.hash_key(raw_key)
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(APIKey).where(APIKey.key_hash == key_hash, APIKey.is_active == True)
    )
    api_key = result.scalar_one_or_none()
    if not api_key:
        return None
    if api_key.expires_at and api_key.expires_at < now:
        return None
    if not api_key.permissions.get(permission, False):
        raise HTTPException(status_code=403, detail=f"API ключ не имеет права: {permission}")
    api_key.last_used_at = now
    await db.flush()
    result = await db.execute(
        select(User).where(User.id == api_key.user_id, User.is_active == True)
    )
    return result.scalar_one_or_none()


# ── Unified auth dependency ───────────────────────────────────────────────────

async def get_current_user(
    request: Request,
    db: AsyncSession,
    permission: str = "read",
) -> User:
    """
    Поддерживает два метода:
    1. Authorization: Bearer <JWT>
    2. Authorization: Bearer <API_KEY>  или  X-API-Key: <API_KEY>
    """
    # Извлекаем токен из заголовка
    auth_header = request.headers.get("Authorization", "")
    x_api_key = request.headers.get("X-API-Key", "")

    token: str | None = None
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
    elif x_api_key:
        token = x_api_key

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Необходима аутентификация. Используйте Bearer токен или X-API-Key.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 1. Пробуем JWT
    try:
        payload = _decode_token(token)
        if payload.get("type") == "access":
            user_id = int(payload["sub"])
            result = await db.execute(
                select(User).where(User.id == user_id, User.is_active == True)
            )
            user = result.scalar_one_or_none()
            if user:
                return user
    except HTTPException:
        pass  # не JWT — пробуем API Key

    # 2. Пробуем API Key
    user = await _auth_via_api_key(token, db, permission)
    if user:
        return user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Неверный токен или API ключ.",
        headers={"WWW-Authenticate": "Bearer"},
    )
