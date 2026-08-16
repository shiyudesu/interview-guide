from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from interview_guide.common.db.models import InterviewSchedule
from interview_guide.modules.interview_schedule.models import InterviewStatus


class InterviewScheduleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, entity: InterviewSchedule) -> InterviewSchedule:
        self._session.add(entity)
        await self._session.flush()
        return entity

    async def get(self, schedule_id: int) -> InterviewSchedule | None:
        return await self._session.get(InterviewSchedule, schedule_id)

    async def list_all(self) -> list[InterviewSchedule]:
        result = await self._session.scalars(select(InterviewSchedule))
        return list(result)

    async def list_by_status(
        self,
        status: InterviewStatus,
    ) -> list[InterviewSchedule]:
        result = await self._session.scalars(
            select(InterviewSchedule).where(InterviewSchedule.status == status.value)
        )
        return list(result)

    async def list_between(
        self,
        start: datetime,
        end: datetime,
    ) -> list[InterviewSchedule]:
        result = await self._session.scalars(
            select(InterviewSchedule).where(InterviewSchedule.interview_time.between(start, end))
        )
        return list(result)

    async def delete(self, schedule_id: int) -> None:
        await self._session.execute(
            delete(InterviewSchedule).where(InterviewSchedule.id == schedule_id)
        )

    async def expire_pending(self, cutoff: datetime) -> int:
        result = await self._session.execute(
            update(InterviewSchedule)
            .where(
                InterviewSchedule.status == InterviewStatus.PENDING.value,
                InterviewSchedule.interview_time < cutoff,
            )
            .values(status=InterviewStatus.CANCELLED.value)
            .returning(InterviewSchedule.id)
        )
        return len(result.scalars().all())
