from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from interview_guide.common.db.models import (
    InterviewQuestionRecord,
    InterviewSession,
    InterviewTurnRecord,
    Resume,
    ResumeAnalysis,
)


@dataclass(frozen=True)
class ResumeListRow:
    resume: Resume
    latest_score: int | None
    last_analyzed_at: datetime | None
    interview_count: int


class ResumeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_rows(
        self,
        *,
        ids: list[int] | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[ResumeListRow]:
        latest = select(
            ResumeAnalysis.resume_id.label("resume_id"),
            ResumeAnalysis.overall_score.label("latest_score"),
            ResumeAnalysis.analyzed_at.label("last_analyzed_at"),
            func.row_number()
            .over(
                partition_by=ResumeAnalysis.resume_id,
                order_by=ResumeAnalysis.analyzed_at.desc(),
            )
            .label("row_number"),
        ).subquery()
        counts = (
            select(
                InterviewSession.resume_id.label("resume_id"),
                func.count(InterviewSession.id).label("interview_count"),
            )
            .where(InterviewSession.resume_id.is_not(None))
            .group_by(InterviewSession.resume_id)
            .subquery()
        )
        statement = (
            select(
                Resume,
                latest.c.latest_score,
                latest.c.last_analyzed_at,
                func.coalesce(counts.c.interview_count, 0),
            )
            .outerjoin(
                latest,
                (latest.c.resume_id == Resume.id) & (latest.c.row_number == 1),
            )
            .outerjoin(counts, counts.c.resume_id == Resume.id)
            .order_by(Resume.uploaded_at.desc())
        )
        if ids is not None:
            statement = statement.where(Resume.id.in_(ids))
        if offset:
            statement = statement.offset(offset)
        if limit is not None:
            statement = statement.limit(limit)
        result = await self._session.execute(statement)
        return [
            ResumeListRow(
                resume=row[0],
                latest_score=row[1],
                last_analyzed_at=row[2],
                interview_count=int(row[3]),
            )
            for row in result.all()
        ]

    async def get(self, resume_id: int) -> Resume | None:
        return await self._session.get(Resume, resume_id)

    async def get_by_hash(self, file_hash: str) -> Resume | None:
        result = await self._session.scalars(select(Resume).where(Resume.file_hash == file_hash))
        return result.first()

    async def add(self, resume: Resume) -> Resume:
        self._session.add(resume)
        await self._session.flush()
        return resume

    async def analyses(self, resume_id: int) -> list[ResumeAnalysis]:
        result = await self._session.scalars(
            select(ResumeAnalysis)
            .where(ResumeAnalysis.resume_id == resume_id)
            .order_by(ResumeAnalysis.analyzed_at.desc())
        )
        return list(result)

    async def latest_analysis(
        self,
        resume_id: int,
    ) -> ResumeAnalysis | None:
        result = await self._session.scalars(
            select(ResumeAnalysis)
            .where(ResumeAnalysis.resume_id == resume_id)
            .order_by(ResumeAnalysis.analyzed_at.desc())
            .limit(1)
        )
        return result.first()

    async def delete_graph(self, resume_id: int) -> None:
        session_ids = select(InterviewSession.id).where(InterviewSession.resume_id == resume_id)
        await self._session.execute(
            update(InterviewSession)
            .where(InterviewSession.resume_id == resume_id)
            .values(current_question_id=None)
        )
        await self._session.execute(
            delete(InterviewTurnRecord).where(
                InterviewTurnRecord.interview_session_id.in_(session_ids)
            )
        )
        await self._session.execute(
            delete(InterviewQuestionRecord).where(
                InterviewQuestionRecord.interview_session_id.in_(session_ids)
            )
        )
        await self._session.execute(
            delete(InterviewSession).where(InterviewSession.resume_id == resume_id)
        )
        await self._session.execute(
            delete(ResumeAnalysis).where(ResumeAnalysis.resume_id == resume_id)
        )
        await self._session.execute(delete(Resume).where(Resume.id == resume_id))
