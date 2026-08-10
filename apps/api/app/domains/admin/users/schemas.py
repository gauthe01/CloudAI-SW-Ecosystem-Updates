import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.db.models.identity import RoleType, UserStatus


class AdminUserResponse(BaseModel):
    user_id: uuid.UUID
    email: str
    display_name: str
    status: UserStatus
    roles: list[RoleType]
    created_at: datetime
    updated_at: datetime
    deactivated_at: datetime | None


class AdminUserListResponse(BaseModel):
    users: list[AdminUserResponse]


class AdminUserCreateRequest(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=240)
    roles: list[RoleType] = Field(min_length=1)

    @field_validator("roles")
    @classmethod
    def roles_must_be_unique(cls, roles: list[RoleType]) -> list[RoleType]:
        return unique_roles(roles)


class AdminUserUpdateRequest(BaseModel):
    email: EmailStr | None = None
    display_name: str | None = Field(default=None, min_length=1, max_length=240)
    roles: list[RoleType] | None = Field(default=None, min_length=1)

    @field_validator("roles")
    @classmethod
    def roles_must_be_unique(cls, roles: list[RoleType] | None) -> list[RoleType] | None:
        if roles is None:
            return None
        return unique_roles(roles)


def unique_roles(roles: list[RoleType]) -> list[RoleType]:
    seen: set[RoleType] = set()
    unique: list[RoleType] = []
    for role in roles:
        if role not in seen:
            unique.append(role)
            seen.add(role)
    return unique
