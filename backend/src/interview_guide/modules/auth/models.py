from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import field_validator

from interview_guide.common.api.models import CamelModel


class RegisterRequest(CamelModel):
    email: str
    password: str
    display_name: str | None = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalized_email(value)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        validate_password_length(value)
        return value


class EmailRequest(CamelModel):
    email: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalized_email(value)


class ActionTokenRequest(CamelModel):
    token: str

    @field_validator("token")
    @classmethod
    def validate_token(cls, value: str) -> str:
        token = value.strip()
        if not token or len(token) > 256:
            raise ValueError("链接 Token 无效")
        return token


class PasswordResetConfirmRequest(ActionTokenRequest):
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        validate_password_length(value)
        return value


class LoginRequest(CamelModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalized_email(value)


class ChangePasswordRequest(CamelModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        validate_password_length(value)
        return value


class UserResponse(CamelModel):
    id: UUID
    email: str
    display_name: str | None
    role: str
    status: str
    created_at: datetime


class AuthSessionResponse(CamelModel):
    user: UserResponse
    csrf_token: str


class AuthConfigResponse(CamelModel):
    auth_enabled: bool
    registration_enabled: bool


class RegistrationResponse(CamelModel):
    email: str
    verification_required: bool


def normalized_email(value: str) -> str:
    normalized = value.strip().casefold()
    if (
        not normalized
        or len(normalized) > 320
        or normalized.count("@") != 1
        or any(character.isspace() for character in normalized)
    ):
        raise ValueError("邮箱格式无效")
    local, domain = normalized.rsplit("@", 1)
    if (
        not local
        or not domain
        or "." not in domain
        or domain.startswith(".")
        or domain.endswith(".")
    ):
        raise ValueError("邮箱格式无效")
    return normalized


def validate_password_length(value: str) -> None:
    if len(value) < 6:
        raise ValueError("密码至少需要 6 个字符")
    if len(value) > 128:
        raise ValueError("密码不能超过 128 个字符")
