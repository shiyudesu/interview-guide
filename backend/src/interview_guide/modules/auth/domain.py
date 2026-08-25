from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class UserRole(StrEnum):
    USER = "USER"
    ADMIN = "ADMIN"


@dataclass(frozen=True)
class Actor:
    user_id: UUID
    role: UserRole
    session_id: str
    csrf_token: str
