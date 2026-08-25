from __future__ import annotations

from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from interview_guide.common.db.models import InterviewSchedule
from interview_guide.modules.interview_schedule.models import InterviewStatus


class InterviewScheduleRepository:
    def __init__(self, session: AsyncSession, user_id: UUID | None = None) -> None:
        self._session = session
        self._user_id = user_id

    async def add(self, entity: InterviewSchedule) -> InterviewSchedule:
        if self._user_id is not None:
            entity.user_id = self._user_id
        self._session.add(entity)
        await self._session.flush()
        return entity

    async def get(self, schedule_id: int) -> InterviewSchedule | None:
        statement = select(InterviewSchedule).where(InterviewSchedule.id == schedule_id)
        if self._user_id is not None:
            statement = statement.where(InterviewSchedule.user_id == self._user_id)
        return cast(InterviewSchedule | None, await self._session.scalar(statement))

    async def list_all(self) -> list[InterviewSchedule]:
        statement = select(InterviewSchedule)
        if self._user_id is not None:
            statement = statement.where(InterviewSchedule.user_id == self._user_id)
        result = await self._session.scalars(statement)
        return list(result)

    async def list_by_status(
        self,
        status: InterviewStatus,
    ) -> list[InterviewSchedule]:
        statement = select(InterviewSchedule).where(InterviewSchedule.status == status.value)
        if self._user_id is not None:
            statement = statement.where(InterviewSchedule.user_id == self._user_id)
        result = await self._session.scalars(statement)
        return list(result)

    async def list_between(
        self,
        start: datetime,
        end: datetime,
    ) -> list[InterviewSchedule]:
        statement = select(InterviewSchedule).where(
            InterviewSchedule.interview_time.between(start, end)
        )
        if self._user_id is not None:
            statement = statement.where(InterviewSchedule.user_id == self._user_id)
        result = await self._session.scalars(statement)
        return list(result)

    async def delete(self, schedule_id: int) -> None:
        statement = delete(InterviewSchedule).where(InterviewSchedule.id == schedule_id)
        if self._user_id is not None:
            statement = statement.where(InterviewSchedule.user_id == self._user_id)
        await self._session.execute(statement)

    async def expire_pending(self, cutoff: datetime) -> int:
        statement = (
            update(InterviewSchedule)
            .where(
                InterviewSchedule.status == InterviewStatus.PENDING.value,
                InterviewSchedule.interview_time < cutoff,
            )
            .values(status=InterviewStatus.CANCELLED.value)
            .returning(InterviewSchedule.id)
        )
        if self._user_id is not None:
            statement = statement.where(InterviewSchedule.user_id == self._user_id)
        result = await self._session.execute(statement)
        return len(result.scalars().all())
