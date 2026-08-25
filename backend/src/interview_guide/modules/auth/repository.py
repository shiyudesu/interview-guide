from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from interview_guide.common.ai.user_providers import ensure_user_provider_defaults
from interview_guide.common.config.settings import Settings
from interview_guide.common.db.models import (
    LEGACY_OWNER_ID,
    InterviewSchedule,
    InterviewSession,
    KnowledgeBase,
    RagChatSession,
    Resume,
    UserAccount,
    UserAiSetting,
    UserLlmProviderConfig,
    UserPasswordCredential,
    UserVoiceSetting,
    VoiceInterviewSession,
)
from interview_guide.common.errors import BusinessException, ErrorCode


@dataclass(frozen=True)
class LoginRecord:
    user: UserAccount
    credential: UserPasswordCredential


class AuthRepository:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        settings: Settings | None = None,
    ) -> None:
        self._sessions = sessions
        self._settings = settings

    async def find_login(self, email: str) -> LoginRecord | None:
        async with self._sessions() as session:
            row = (
                await session.execute(
                    select(UserAccount, UserPasswordCredential)
                    .join(
                        UserPasswordCredential,
                        UserPasswordCredential.user_id == UserAccount.id,
                    )
                    .where(func.lower(UserAccount.email) == email)
                )
            ).one_or_none()
            return LoginRecord(row[0], row[1]) if row is not None else None

    async def get_user(self, user_id: UUID) -> UserAccount | None:
        async with self._sessions() as session:
            return await session.get(UserAccount, user_id)

    async def get_user_by_email(self, email: str) -> UserAccount | None:
        async with self._sessions() as session:
            return cast(
                UserAccount | None,
                await session.scalar(
                    select(UserAccount).where(func.lower(UserAccount.email) == email)
                ),
            )

    async def create_human_user(
        self,
        *,
        email: str,
        display_name: str | None,
        password_hash: str,
        role: str,
        status: str,
        now: datetime,
        email_verified: bool,
    ) -> UserAccount:
        entity = UserAccount(
            id=uuid4(),
            email=email,
            display_name=display_name.strip() if display_name and display_name.strip() else None,
            kind="HUMAN",
            role=role,
            status=status,
            email_verified_at=now if email_verified else None,
            created_at=now,
            updated_at=now,
        )
        credential = UserPasswordCredential(
            user_id=entity.id,
            password_hash=password_hash,
            password_changed_at=now,
            created_at=now,
            updated_at=now,
        )
        try:
            async with self._sessions() as session, session.begin():
                session.add(entity)
                session.add(credential)
                if self._settings is not None:
                    await ensure_user_provider_defaults(
                        session,
                        entity.id,
                        self._settings,
                        now,
                    )
        except IntegrityError as error:
            raise BusinessException(ErrorCode.USER_ALREADY_EXISTS, "该邮箱已注册") from error
        return entity

    async def update_password(self, user_id: UUID, password_hash: str, now: datetime) -> None:
        async with self._sessions() as session, session.begin():
            credential = await session.get(UserPasswordCredential, user_id, with_for_update=True)
            if credential is None:
                raise BusinessException(ErrorCode.AUTH_INVALID_CREDENTIALS)
            credential.password_hash = password_hash
            credential.password_changed_at = now
            credential.updated_at = now

    async def rehash_password(self, user_id: UUID, password_hash: str, now: datetime) -> None:
        async with self._sessions() as session, session.begin():
            credential = await session.get(UserPasswordCredential, user_id, with_for_update=True)
            if credential is not None:
                credential.password_hash = password_hash
                credential.updated_at = now

    async def claim_legacy_resources(self, user_id: UUID) -> dict[str, int]:
        tables = (
            InterviewSchedule,
            Resume,
            InterviewSession,
            KnowledgeBase,
            RagChatSession,
            VoiceInterviewSession,
        )
        counts: dict[str, int] = {}
        async with self._sessions() as session, session.begin():
            for model in tables:
                result = cast(
                    CursorResult[Any],
                    await session.execute(
                        update(model)
                        .where(model.user_id == LEGACY_OWNER_ID)
                        .values(user_id=user_id)
                    ),
                )
                counts[model.__tablename__] = int(result.rowcount or 0)
            legacy_providers = list(
                await session.scalars(
                    select(UserLlmProviderConfig).where(
                        UserLlmProviderConfig.user_id == LEGACY_OWNER_ID
                    )
                )
            )
            if legacy_providers:
                await session.execute(
                    delete(UserVoiceSetting).where(UserVoiceSetting.user_id == user_id)
                )
                await session.execute(delete(UserAiSetting).where(UserAiSetting.user_id == user_id))
                await session.execute(
                    delete(UserLlmProviderConfig).where(UserLlmProviderConfig.user_id == user_id)
                )
                await session.execute(
                    update(UserLlmProviderConfig)
                    .where(UserLlmProviderConfig.user_id == LEGACY_OWNER_ID)
                    .values(user_id=user_id)
                )
                await session.execute(
                    update(UserAiSetting)
                    .where(UserAiSetting.user_id == LEGACY_OWNER_ID)
                    .values(user_id=user_id)
                )
                await session.execute(
                    update(UserVoiceSetting)
                    .where(UserVoiceSetting.user_id == LEGACY_OWNER_ID)
                    .values(user_id=user_id)
                )
                counts["user_llm_providers"] = len(legacy_providers)
        return counts
