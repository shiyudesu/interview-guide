from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from interview_guide.common.db.models import Resume
from interview_guide.common.errors import BusinessException, ErrorCode
from interview_guide.infrastructure.storage.s3 import S3Storage
from interview_guide.modules.resume.models import (
    ResumeDetailResponse,
    ResumeListResponse,
)
from interview_guide.modules.resume.repository import ResumeRepository

logger = logging.getLogger(__name__)


class ResumeService:
    def __init__(
        self,
        session: AsyncSession,
        storage: S3Storage,
    ) -> None:
        self._session = session
        self._repository = ResumeRepository(session)
        self._storage = storage

    async def list(self) -> list[ResumeListResponse]:
        return [
            ResumeListResponse(
                id=row.resume.id,
                filename=row.resume.original_filename,
                file_size=row.resume.file_size,
                uploaded_at=row.resume.uploaded_at,
                access_count=row.resume.access_count,
                latest_score=row.latest_score,
                last_analyzed_at=row.last_analyzed_at,
                interview_count=row.interview_count,
                analyze_status=row.resume.analyze_status,
                analyze_error=row.resume.analyze_error,
            )
            for row in await self._repository.list_rows()
        ]

    async def detail(self, resume_id: int) -> ResumeDetailResponse:
        resume = await self._required(resume_id)
        return ResumeDetailResponse(
            id=resume.id,
            filename=resume.original_filename,
            file_size=resume.file_size,
            content_type=resume.content_type,
            storage_url=resume.storage_url,
            uploaded_at=resume.uploaded_at,
            access_count=resume.access_count,
            resume_text=resume.resume_text,
            analyze_status=resume.analyze_status,
            analyze_error=resume.analyze_error,
            analyses=[],
            interviews=[],
        )

    async def delete(self, resume_id: int) -> None:
        resume = await self._required(resume_id)
        storage_key = resume.storage_key
        await self._session.rollback()
        try:
            await self._storage.delete(storage_key)
        except Exception:
            logger.warning(
                "storage delete failed; continuing database delete resumeId=%s",
                resume_id,
                exc_info=True,
            )
        async with self._session.begin():
            await self._repository.delete_graph(resume_id)

    async def _required(self, resume_id: int) -> Resume:
        resume = await self._repository.get(resume_id)
        if resume is None:
            raise BusinessException(ErrorCode.RESUME_NOT_FOUND)
        return resume
