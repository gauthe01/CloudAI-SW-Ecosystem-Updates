import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.db.models.identity import RoleType


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)
    keep_signed_in: bool = False


class UserResponse(BaseModel):
    user_id: uuid.UUID
    email: str
    display_name: str
    roles: list[RoleType]


class AuthContextResponse(BaseModel):
    user: UserResponse
    available_views: list[RoleType]
    active_view: RoleType


class SessionResponse(BaseModel):
    user: UserResponse
    expires_at: datetime
    available_views: list[RoleType]
    active_view: RoleType


class AuthMeResponse(BaseModel):
    user: UserResponse
    available_views: list[RoleType]
    active_view: RoleType


class SwitchActiveViewRequest(BaseModel):
    active_view: RoleType


class LogoutResponse(BaseModel):
    status: str = "ok"
