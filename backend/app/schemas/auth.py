from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: Optional[str] = None


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 3600


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class UserOut(BaseModel):
    id: int
    email: str
    full_name: Optional[str]
    is_active: bool
    is_superuser: bool
    created_at: datetime
    last_login_at: Optional[datetime]

    model_config = {"from_attributes": True}


class APIKeyCreate(BaseModel):
    name: str = Field(..., description="Название ключа, напр. 'Production'")
    expires_days: Optional[int] = Field(365, description="Срок жизни в днях, null = бессрочный")
    permissions: dict = Field(
        default={"read": True, "write": True, "delete": False}
    )


class APIKeyOut(BaseModel):
    id: int
    name: str
    key_prefix: str
    permissions: dict
    expires_at: Optional[datetime]
    last_used_at: Optional[datetime]
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class APIKeyCreated(APIKeyOut):
    """Возвращается ТОЛЬКО при создании — содержит полный ключ."""
    key: str
