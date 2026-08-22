from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from interview_guide.common.db.models import Resume, ResumeAnalysis
from interview_guide.common.errors import BusinessException, ErrorCode
from interview_guide.common.redis.streams import (
    RESUME_ANALYZE,
    RedisStreamService,
)
from interview_guide.common.runtime import BlockingExecutor
from interview_guide.infrastructure.export.pdf import (
    PdfDocumentBuilder,
    ScoreRow,
    pdf_download_headers,
)
from interview_guide.infrastructure.file.content_type import ContentTypeDetector
from interview_guide.infrastructure.file.document import AsyncDocumentParser
from interview_guide.infrastructure.file.hash import sha256_bytes
from interview_guide.infrastructure.file.validation import (
    RESUME_MAX_BYTES,
    validate_content_type_by_list,
    validate_file,
)
from interview_guide.infrastructure.storage.s3 import S3Storage
from interview_guide.modules.interview.evaluation import parse_saved_list
from interview_guide.modules.resume.models import (
    ResumeAnalysisHistoryResponse,
    ResumeDetailResponse,
    ResumeInterviewResponse,
    ResumeListResponse,
)
from interview_guide.modules.resume.repository import ResumeRepository

logger = logging.getLogger(__name__)


class ResumeService:
    def __init__(
        self,
        session: AsyncSession,
        storage: S3Storage,
        streams: RedisStreamService | None = None,
        parser: AsyncDocumentParser | None = None,
        blocking_executor: BlockingExecutor | None = None,
        now: datetime | None = None,
    ) -> None:
        self._session = session
        self._repository = ResumeRepository(session)
        self._storage = storage
        self._streams = streams
        self._parser = parser
        self._blocking_executor = blocking_executor
        self._now = now or datetime.now()

    async def list(
        self,
        *,
        ids: list[int] | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[ResumeListResponse]:
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
            for row in await self._repository.list_rows(
                ids=ids,
                limit=limit,
                offset=offset,
            )
        ]

    async def detail(self, resume_id: int) -> ResumeDetailResponse:
        resume = await self._required(resume_id)
        analyses = await self._repository.analyses(resume_id)
        interviews = await self._repository.interviews(resume_id)
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
            analyses=[
                ResumeAnalysisHistoryResponse(
                    id=analysis.id,
                    overall_score=analysis.overall_score,
                    content_score=analysis.content_score,
                    structure_score=analysis.structure_score,
                    skill_match_score=analysis.skill_match_score,
                    expression_score=analysis.expression_score,
                    project_score=analysis.project_score,
                    summary=analysis.summary,
                    analyzed_at=analysis.analyzed_at,
                    strengths=parse_saved_list(analysis.strengths_json),
                    suggestions=json.loads(analysis.suggestions_json or "[]"),
                )
                for analysis in analyses
            ],
            interviews=[
                ResumeInterviewResponse(
                    id=interview.id,
                    session_id=interview.session_id,
                    channel=interview.channel,
                    planned_main_questions=interview.planned_main_question_count,
                    status=interview.status,
                    evaluate_status=interview.evaluate_status,
                    evaluate_error=interview.evaluate_error,
                    overall_score=interview.overall_score,
                    overall_feedback=interview.overall_feedback,
                    created_at=interview.created_at,
                    completed_at=interview.completed_at,
                    strengths=parse_saved_list(interview.strengths_json),
                    improvements=parse_saved_list(interview.improvements_json),
                )
                for interview in interviews
            ],
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

    async def upload(
        self,
        data: bytes,
        filename: str | None,
        upload_content_type: str | None,
    ) -> dict[str, object]:
        if self._streams is None or self._parser is None:
            raise RuntimeError("Resume upload dependencies are unavailable")
        validate_file(data, RESUME_MAX_BYTES, "简历")
        detected_type = ContentTypeDetector().detect(
            data,
            filename,
            upload_content_type,
        )
        validate_content_type_by_list(
            detected_type,
            (
                "application/pdf",
                "application/msword",
                ("application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
                "text/plain",
            ),
            f"不支持的文件类型: {detected_type}",
        )
        file_hash = sha256_bytes(data)
        existing = await self._repository.get_by_hash(file_hash)
        if existing is not None:
            existing.access_count = (existing.access_count or 0) + 1
            existing.last_accessed_at = self._now
            analysis = await self._repository.latest_analysis(existing.id)
            await self._session.commit()
            if analysis is not None:
                return {
                    "analysis": self._analysis_response(existing, analysis),
                    "storage": {
                        "fileKey": existing.storage_key or "",
                        "fileUrl": existing.storage_url or "",
                        "resumeId": existing.id,
                    },
                    "duplicate": True,
                }
            return self._upload_response(existing, duplicate=True)
        await self._session.rollback()

        resume_text = await self._parser.parse(
            data,
            filename,
            detected_type,
        )
        if not resume_text.strip():
            raise BusinessException(
                ErrorCode.RESUME_PARSE_FAILED,
                "无法从文件中提取文本内容，请确保文件不是扫描版PDF",
            )
        file_key = await self._storage.upload(
            data,
            filename,
            upload_content_type,
            "resumes",
        )
        file_url = self._storage.object_url(file_key)
        try:
            async with self._session.begin():
                resume = await self._repository.add(
                    Resume(
                        access_count=1,
                        analyze_error=None,
                        analyze_status="PENDING",
                        content_type=upload_content_type,
                        file_hash=file_hash,
                        file_size=len(data),
                        last_accessed_at=self._now,
                        original_filename=filename or "",
                        resume_text=resume_text,
                        storage_key=file_key,
                        storage_url=file_url,
                        uploaded_at=self._now,
                    )
                )
        except Exception:
            await self._storage.delete(file_key)
            raise
        try:
            await self._streams.add(
                RESUME_ANALYZE.key,
                {
                    "resumeId": str(resume.id),
                    "content": resume_text,
                    "retryCount": "0",
                },
            )
        except Exception as error:
            async with self._session.begin():
                stored = await self._repository.get(resume.id)
                if stored is not None:
                    stored.analyze_status = "FAILED"
                    stored.analyze_error = f"任务入队失败: {error}"[:500]
        return self._upload_response(resume, duplicate=False)

    async def reanalyze(self, resume_id: int) -> None:
        if self._streams is None or self._parser is None:
            raise RuntimeError("Resume analysis dependencies are unavailable")
        resume = await self._required(resume_id)
        resume_text = resume.resume_text
        if resume_text is None or not resume_text.strip():
            storage_key = resume.storage_key
            filename = resume.original_filename
            content_type = resume.content_type
            await self._session.rollback()
            if not storage_key:
                raise BusinessException(
                    ErrorCode.RESUME_PARSE_FAILED,
                    "无法获取简历文本内容",
                )
            data = await self._storage.download(storage_key)
            resume_text = await self._parser.parse(
                data,
                filename,
                content_type,
            )
            if not resume_text.strip():
                raise BusinessException(
                    ErrorCode.RESUME_PARSE_FAILED,
                    "无法获取简历文本内容",
                )
        else:
            await self._session.rollback()
        async with self._session.begin():
            stored = await self._repository.get(resume_id)
            if stored is None:
                raise BusinessException(
                    ErrorCode.RESUME_NOT_FOUND,
                    "简历不存在",
                )
            if not stored.resume_text or not stored.resume_text.strip():
                stored.resume_text = resume_text
            stored.analyze_status = "PENDING"
            stored.analyze_error = None
        try:
            await self._streams.add(
                RESUME_ANALYZE.key,
                {
                    "resumeId": str(resume_id),
                    "content": resume_text,
                    "retryCount": "0",
                },
            )
        except Exception as error:
            async with self._session.begin():
                stored = await self._repository.get(resume_id)
                if stored is not None:
                    stored.analyze_status = "FAILED"
                    stored.analyze_error = f"任务入队失败: {error}"[:500]

    async def export_pdf(self, resume_id: int) -> tuple[bytes, dict[str, str]]:
        resume = await self._required(resume_id)
        analysis = await self._repository.latest_analysis(resume_id)
        if analysis is None:
            raise BusinessException(ErrorCode.RESUME_ANALYSIS_NOT_FOUND)
        font = Path(__file__).resolve().parents[4] / "resources/fonts/ZhuqueFangsong-Regular.ttf"
        strengths = json.loads(analysis.strengths_json or "[]")
        suggestions = json.loads(analysis.suggestions_json or "[]")
        sections: list[tuple[str, list[str]]] = [
            (
                "基本信息",
                [
                    f"文件名: {resume.original_filename}",
                    f"上传时间: {resume.uploaded_at:%Y-%m-%d %H:%M:%S}",
                ],
            ),
            (
                "综合评分",
                [f"总分: {analysis.overall_score} / 100"],
            ),
        ]
        if analysis.summary is not None:
            sections.append(("简历摘要", [analysis.summary]))
        if strengths:
            sections.append(("优势亮点", [f"• {item}" for item in strengths]))
        if suggestions:
            paragraphs: list[str] = []
            for suggestion in suggestions:
                paragraphs.extend(
                    [
                        (f"【{suggestion.get('priority')}】{suggestion.get('category')}"),
                        f"问题: {suggestion.get('issue')}",
                        f"建议: {suggestion.get('recommendation')}",
                    ]
                )
            sections.append(("改进建议", paragraphs))
        if self._blocking_executor is None:
            raise RuntimeError("Resume PDF export executor is unavailable")
        pdf = await self._blocking_executor.run(
            PdfDocumentBuilder(font).build,
            "简历分析报告",
            sections,
            score_rows=[
                ScoreRow("项目经验", analysis.project_score or 0, 40),
                ScoreRow("技能匹配度", analysis.skill_match_score or 0, 20),
                ScoreRow("内容完整性", analysis.content_score or 0, 15),
                ScoreRow("结构清晰度", analysis.structure_score or 0, 15),
                ScoreRow("表达专业性", analysis.expression_score or 0, 10),
            ],
            score_after_sections=2,
            page_break_after_titles=frozenset({"改进建议"}),
        )
        filename = f"简历分析报告_{resume.original_filename}.pdf"
        return pdf, pdf_download_headers(filename)

    @staticmethod
    def _upload_response(
        resume: Resume,
        *,
        duplicate: bool,
    ) -> dict[str, object]:
        return {
            "resume": {
                "analyzeStatus": resume.analyze_status or "PENDING",
                "filename": resume.original_filename,
                "id": resume.id,
            },
            "storage": {
                "resumeId": resume.id,
                "fileUrl": resume.storage_url or "",
                "fileKey": resume.storage_key or "",
            },
            "duplicate": duplicate,
        }

    @staticmethod
    def _analysis_response(
        resume: Resume,
        analysis: ResumeAnalysis,
    ) -> dict[str, object]:
        return {
            "overallScore": analysis.overall_score,
            "scoreDetail": {
                "contentScore": analysis.content_score,
                "structureScore": analysis.structure_score,
                "skillMatchScore": analysis.skill_match_score,
                "expressionScore": analysis.expression_score,
                "projectScore": analysis.project_score,
            },
            "summary": analysis.summary,
            "strengths": json.loads(analysis.strengths_json or "[]"),
            "suggestions": json.loads(analysis.suggestions_json or "[]"),
            "originalText": resume.resume_text,
        }

    async def _required(self, resume_id: int) -> Resume:
        resume = await self._repository.get(resume_id)
        if resume is None:
            raise BusinessException(ErrorCode.RESUME_NOT_FOUND)
        return resume
