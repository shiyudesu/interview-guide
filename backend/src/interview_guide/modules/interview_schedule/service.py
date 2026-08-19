from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from interview_guide.common.db.models import InterviewSchedule
from interview_guide.common.errors import BusinessException, ErrorCode
from interview_guide.modules.interview_schedule.models import (
    CreateInterviewRequest,
    InterviewScheduleResponse,
    InterviewStatus,
)
from interview_guide.modules.interview_schedule.repository import (
    InterviewScheduleRepository,
)


class InterviewScheduleService:
    def __init__(
        self,
        session: AsyncSession,
        now: Callable[[], datetime] = datetime.now,
    ) -> None:
        self._session = session
        self._repository = InterviewScheduleRepository(session)
        self._now = now

    async def create(
        self,
        request: CreateInterviewRequest,
    ) -> InterviewScheduleResponse:
        timestamp = self._now()
        async with self._session.begin():
            entity = await self._repository.add(
                InterviewSchedule(
                    company_name=request.company_name,
                    position=request.position,
                    interview_time=request.interview_time,
                    interview_type=request.interview_type,
                    meeting_link=request.meeting_link,
                    round_number=request.round_number,
                    interviewer=request.interviewer,
                    notes=request.notes,
                    status=InterviewStatus.PENDING.value,
                    created_at=timestamp,
                    updated_at=timestamp,
                )
            )
        return self._response(entity)

    async def get(self, schedule_id: int) -> InterviewScheduleResponse:
        entity = await self._required(schedule_id)
        return self._response(entity)

    async def list(
        self,
        status: str | None,
        start: datetime | None,
        end: datetime | None,
    ) -> list[InterviewScheduleResponse]:
        if start is not None and end is not None:
            entities = await self._repository.list_between(start, end)
        elif status is not None:
            entities = await self._repository.list_by_status(self._status(status))
        else:
            entities = await self._repository.list_all()
        return [self._response(entity) for entity in entities]

    async def update(
        self,
        schedule_id: int,
        request: CreateInterviewRequest,
    ) -> InterviewScheduleResponse:
        async with self._session.begin():
            entity = await self._required(schedule_id)
            entity.company_name = request.company_name
            entity.position = request.position
            entity.interview_time = request.interview_time
            entity.interview_type = request.interview_type
            entity.meeting_link = request.meeting_link
            entity.round_number = request.round_number
            entity.interviewer = request.interviewer
            entity.notes = request.notes
            entity.updated_at = self._now()
        return self._response(entity)

    async def delete(self, schedule_id: int) -> None:
        async with self._session.begin():
            await self._repository.delete(schedule_id)

    async def update_status(
        self,
        schedule_id: int,
        status: str,
    ) -> InterviewScheduleResponse:
        async with self._session.begin():
            entity = await self._required(schedule_id)
            entity.status = self._status(status).value
            entity.updated_at = self._now()
        return self._response(entity)

    async def expire_pending(self) -> int:
        async with self._session.begin():
            return await self._repository.expire_pending(self._now())

    async def _required(self, schedule_id: int) -> InterviewSchedule:
        entity = await self._repository.get(schedule_id)
        if entity is None:
            raise BusinessException(
                ErrorCode.INTERVIEW_SCHEDULE_NOT_FOUND,
                f"面试日程不存在: {schedule_id}",
            )
        return entity

    @staticmethod
    def _status(value: str) -> InterviewStatus:
        try:
            return InterviewStatus(value)
        except ValueError as error:
            raise ValueError(
                "No enum constant "
                "interview.guide.modules.interviewschedule.model."
                f"InterviewStatus.{value}"
            ) from error

    @staticmethod
    def _response(entity: InterviewSchedule) -> InterviewScheduleResponse:
        return InterviewScheduleResponse(
            company_name=entity.company_name,
            created_at=entity.created_at,
            id=entity.id,
            interview_time=entity.interview_time,
            interview_type=entity.interview_type,
            interviewer=entity.interviewer,
            meeting_link=entity.meeting_link,
            notes=entity.notes,
            position=entity.position,
            round_number=entity.round_number,
            status=InterviewStatus(entity.status),
            updated_at=entity.updated_at,
        )


def schedule_now() -> datetime:
    return datetime.now()
