import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.core.security import password_meets_policy
from app.db.models.account_access_request import AccountAccessRequestStatus
from app.db.models.identity import RoleType
from app.domains.admin.users.schemas import AdminUserResponse, unique_roles


class AccessRequestCreateRequest(BaseModel):
    display_name: str = Field(min_length=2, max_length=240)
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)
    confirm_password: str = Field(min_length=1, max_length=200)

    @field_validator("display_name")
    @classmethod
    def trim_required_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("email")
    @classmethod
    def email_must_be_arm_domain(cls, value: str) -> str:
        email = value.lower()
        if not email.endswith("@arm.com"):
            raise ValueError("Use your ARM email address.")
        return email

    @field_validator("password")
    @classmethod
    def password_must_meet_policy(cls, value: str) -> str:
        if not password_meets_policy(value):
            raise ValueError("Create a stronger password.")
        return value

    @model_validator(mode="after")
    def passwords_must_match(self) -> "AccessRequestCreateRequest":
        if self.password != self.confirm_password:
            raise ValueError("Passwords don't match.")
        return self


class AccessRequestCreateResponse(BaseModel):
    status: AccountAccessRequestStatus
    message: str


class AdminAccessRequestResponse(BaseModel):
    request_id: uuid.UUID
    email: str
    display_name: str
    status: AccountAccessRequestStatus
    requested_at: datetime
    reviewed_at: datetime | None
    reviewed_by: uuid.UUID | None
    created_user_id: uuid.UUID | None


class AdminAccessRequestListResponse(BaseModel):
    requests: list[AdminAccessRequestResponse]


class AdminAccessRequestApproveRequest(BaseModel):
    roles: list[RoleType] = Field(min_length=1)

    @field_validator("roles")
    @classmethod
    def roles_must_be_unique(cls, roles: list[RoleType]) -> list[RoleType]:
        return unique_roles(roles)


class AdminAccessRequestReviewResponse(BaseModel):
    request: AdminAccessRequestResponse
    created_user: AdminUserResponse | None = None
