from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from interview_guide.common.ai.prompts import PromptRepository
from interview_guide.common.ai.providers import ProviderRegistry
from interview_guide.common.ai.structured import StructuredOutputInvoker
from interview_guide.common.db.models import Resume, ResumeAnalysis
from interview_guide.common.errors import ErrorCode
from interview_guide.common.redis.streams import (
    RESUME_ANALYZE,
    RedisStreamService,
    StreamMessage,
)

logger = logging.getLogger(__name__)


class ScoreDetail(BaseModel):
    contentScore: int
    structureScore: int
    skillMatchScore: int
    expressionScore: int
    projectScore: int


class Suggestion(BaseModel):
    category: str
    priority: str
    issue: str
    recommendation: str


class AnalysisOutput(BaseModel):
    overallScore: int
    scoreDetail: ScoreDetail
    summary: str
    strengths: list[str]
    suggestions: list[Suggestion]


@dataclass(frozen=True)
class ResumeAnalysisResult:
    output: AnalysisOutput
    original_text: str


class ResumeGradingService:
    def __init__(
        self,
        registry: ProviderRegistry,
        structured: StructuredOutputInvoker,
        prompts: PromptRepository,
    ) -> None:
        self._registry = registry
        self._structured = structured
        self._prompts = prompts

    async def analyze(
        self,
        resume_text: str,
        provider_id: str | None = None,
    ) -> ResumeAnalysisResult:
        system_prompt = self._prompts.render("resume-analysis-system.st")
        user_prompt = self._prompts.render(
            "resume-analysis-user.st",
            {"resumeText": resume_text},
        )
        schema = json.dumps(
            AnalysisOutput.model_json_schema(),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        output = await self._structured.invoke(
            await self._registry.get_chat(provider_id),
            f"{system_prompt}\n\n{schema}",
            user_prompt,
            AnalysisOutput,
            ErrorCode.RESUME_ANALYSIS_FAILED,
            "简历分析失败：",
        )
        return ResumeAnalysisResult(output, resume_text)


@dataclass(frozen=True)
class AnalyzePayload:
    resume_id: int
    content: str


class ResumeAnalyzeHandler:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        streams: RedisStreamService,
        grading_factory: Callable[[UUID], ResumeGradingService],
        now: Callable[[], datetime],
    ) -> None:
        self._sessions = sessions
        self._streams = streams
        self._grading_factory = grading_factory
        self._now = now

    async def parse(self, message: StreamMessage) -> AnalyzePayload | None:
        resume_id = message.data.get("resumeId")
        content = message.data.get("content")
        if resume_id is None or content is None:
            return None
        return AnalyzePayload(int(resume_id), content)

    async def should_skip(self, payload: AnalyzePayload) -> bool:
        async with self._sessions() as session:
            status = await session.scalar(
                select(Resume.analyze_status).where(Resume.id == payload.resume_id)
            )
            return status is None or status == "COMPLETED"

    async def try_mark_processing(self, payload: AnalyzePayload) -> bool:
        return await self._update_status(payload.resume_id, "PROCESSING", None)

    async def process(self, payload: AnalyzePayload) -> None:
        async with self._sessions() as session:
            context = (
                await session.execute(
                    select(
                        Resume.user_id,
                        Resume.analysis_provider_alias,
                    ).where(Resume.id == payload.resume_id)
                )
            ).one_or_none()
        if context is None:
            return
        result = await self._grading_factory(context.user_id).analyze(
            payload.content,
            context.analysis_provider_alias,
        )
        async with self._sessions() as session, session.begin():
            resume = await session.get(Resume, payload.resume_id)
            if resume is None:
                return
            output = result.output
            session.add(
                ResumeAnalysis(
                    analyzed_at=self._now(),
                    content_score=output.scoreDetail.contentScore,
                    expression_score=output.scoreDetail.expressionScore,
                    overall_score=output.overallScore,
                    project_score=output.scoreDetail.projectScore,
                    skill_match_score=output.scoreDetail.skillMatchScore,
                    strengths_json=json.dumps(
                        output.strengths,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                    structure_score=output.scoreDetail.structureScore,
                    suggestions_json=json.dumps(
                        [item.model_dump() for item in output.suggestions],
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                    summary=output.summary,
                    resume_id=resume.id,
                )
            )

    async def mark_completed(self, payload: AnalyzePayload) -> None:
        await self._update_status(payload.resume_id, "COMPLETED", None)

    async def retry(self, payload: AnalyzePayload, retry_count: int) -> None:
        try:
            await self._streams.add(
                RESUME_ANALYZE.key,
                {
                    "resumeId": str(payload.resume_id),
                    "content": payload.content,
                    "retryCount": str(retry_count),
                },
            )
        except Exception as error:
            await self._update_status(
                payload.resume_id,
                "FAILED",
                f"重试入队失败: {error}"[:500],
            )

    async def mark_failed(self, payload: AnalyzePayload, error: str) -> None:
        await self._update_status(payload.resume_id, "FAILED", error)

    async def _update_status(
        self,
        resume_id: int,
        status: str,
        error: str | None,
    ) -> bool:
        async with self._sessions() as session, session.begin():
            resume = await session.get(Resume, resume_id)
            if resume is None:
                return False
            resume.analyze_status = status
            resume.analyze_error = error
            return True
