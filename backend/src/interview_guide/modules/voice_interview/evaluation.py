from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from interview_guide.common.ai.providers import LlmProviderRegistry
from interview_guide.common.db.models import (
    VoiceInterviewEvaluation,
    VoiceInterviewMessage,
    VoiceInterviewSession,
)
from interview_guide.common.errors import BusinessException, ErrorCode
from interview_guide.common.redis.streams import (
    FIELD_RETRY_COUNT,
    FIELD_VOICE_SESSION_ID,
    VOICE_EVALUATE,
    RedisStreamService,
    StreamMessage,
)
from interview_guide.modules.interview.evaluation import (
    QaRecord,
    UnifiedEvaluationService,
)
from interview_guide.modules.interview.models import InterviewReportDTO
from interview_guide.modules.interview.question import InterviewSkillLibrary
from interview_guide.modules.voice_interview.repository import (
    VoiceInterviewRepository,
    trim_to_none,
)


class VoiceEvaluationStatusService(Protocol):
    async def update_evaluate_status(
        self,
        session_id: int,
        status: str,
        error: str | None,
    ) -> None: ...


class VoiceInterviewEvaluationService:
    def __init__(
        self,
        repository: VoiceInterviewRepository,
        unified: UnifiedEvaluationService,
        registry: LlmProviderRegistry,
        skills: InterviewSkillLibrary,
        now: Callable[[], datetime],
    ) -> None:
        self._repository = repository
        self._unified = unified
        self._registry = registry
        self._skills = skills
        self._now = now

    async def generate(self, session_id: int) -> None:
        try:
            session = await self._repository.find_session(session_id)
            if session is None:
                raise BusinessException(
                    ErrorCode.VOICE_SESSION_NOT_FOUND,
                    f"语音面试会话不存在: {session_id}",
                )
            messages = await self._repository.messages(session_id)
            if not messages:
                await self._save_empty(session)
                return
            records = self._build_qa_records(messages)
            provider = await self._registry.get_chat(
                None if session.llm_provider in {None, "", "default"} else session.llm_provider
            )
            report = await self._unified.evaluate(
                provider,
                str(session_id),
                records,
                None,
                self._skills.evaluation_reference_section(session.skill_id),
            )
            await self._save_report(session, report)
        except BusinessException:
            raise
        except Exception as error:
            raise BusinessException(
                ErrorCode.VOICE_EVALUATION_FAILED,
                f"生成评估失败: {error}",
            ) from error

    async def _save_report(
        self,
        session: VoiceInterviewSession,
        report: InterviewReportDTO,
    ) -> None:
        try:
            await self._repository.save_evaluation(
                VoiceInterviewEvaluation(
                    created_at=self._now(),
                    improvements_json=self._compact_json(report.improvements),
                    interview_date=session.start_time,
                    interviewer_role=session.role_type,
                    overall_feedback=report.overall_feedback,
                    overall_score=report.overall_score,
                    question_evaluations_json=self._compact_json(
                        [item.model_dump(by_alias=True) for item in report.question_details]
                    ),
                    reference_answers_json=self._compact_json(
                        [item.model_dump(by_alias=True) for item in report.reference_answers]
                    ),
                    session_id=session.id,
                    strengths_json=self._compact_json(report.strengths),
                )
            )
        except Exception as error:
            raise BusinessException(
                ErrorCode.VOICE_EVALUATION_FAILED,
                f"保存评估失败: {error}",
            ) from error

    async def _save_empty(self, session: VoiceInterviewSession) -> None:
        try:
            await self._repository.save_empty_evaluation(
                session.id,
                session.role_type,
                session.start_time,
            )
        except Exception as error:
            raise BusinessException(
                ErrorCode.VOICE_EVALUATION_FAILED,
                f"保存空评估失败: {error}",
            ) from error

    @staticmethod
    def _compact_json(value: object) -> str:
        return json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
        )

    @classmethod
    def _build_qa_records(
        cls,
        messages: list[VoiceInterviewMessage],
    ) -> list[QaRecord]:
        records: list[QaRecord] = []
        pending_question: tuple[str, str] | None = None
        for message in messages:
            ai_text = trim_to_none(message.ai_generated_text)
            user_text = trim_to_none(message.user_recognized_text)
            if pending_question is not None and user_text is not None:
                records.append(
                    QaRecord(
                        len(records),
                        pending_question[0],
                        pending_question[1],
                        user_text,
                    )
                )
                pending_question = None
                if ai_text is not None:
                    pending_question = (ai_text, cls._infer_category(ai_text))
                continue
            if pending_question is not None:
                records.append(
                    QaRecord(
                        len(records),
                        pending_question[0],
                        pending_question[1],
                        None,
                    )
                )
                pending_question = None
            if ai_text is not None and user_text is not None:
                records.append(
                    QaRecord(
                        len(records),
                        ai_text,
                        cls._infer_category(ai_text),
                        user_text,
                    )
                )
            elif ai_text is not None:
                pending_question = (ai_text, cls._infer_category(ai_text))
            elif user_text is not None:
                records.append(QaRecord(len(records), "", "综合", user_text))
        if pending_question is not None:
            records.append(
                QaRecord(
                    len(records),
                    pending_question[0],
                    pending_question[1],
                    None,
                )
            )
        return records

    @staticmethod
    def _infer_category(ai_text: str | None) -> str:
        if ai_text is None:
            return "综合"
        if any(value in ai_text for value in ("项目", "实习", "工作经历")):
            return "项目深挖"
        if any(value in ai_text for value in ("自我介绍", "介绍一下自己")):
            return "自我介绍"
        if any(value in ai_text for value in ("职业规划", "为什么", "优缺点")):
            return "HR问题"
        return "技术问题"


@dataclass(frozen=True)
class VoiceEvaluatePayload:
    session_id: int


class VoiceEvaluateStreamHandler:
    def __init__(
        self,
        repository: VoiceInterviewRepository,
        streams: RedisStreamService,
        evaluation: VoiceInterviewEvaluationService,
        status_service: VoiceEvaluationStatusService,
    ) -> None:
        self._repository = repository
        self._streams = streams
        self._evaluation = evaluation
        self._status_service = status_service

    async def parse(self, message: StreamMessage) -> VoiceEvaluatePayload | None:
        session_id = message.data.get(FIELD_VOICE_SESSION_ID)
        return VoiceEvaluatePayload(int(session_id)) if session_id is not None else None

    async def should_skip(self, payload: VoiceEvaluatePayload) -> bool:
        session = await self._repository.find_session(payload.session_id)
        return session is None or session.evaluate_status == "COMPLETED"

    async def try_mark_processing(self, payload: VoiceEvaluatePayload) -> bool:
        await self._status_service.update_evaluate_status(
            payload.session_id,
            "PROCESSING",
            None,
        )
        return True

    async def process(self, payload: VoiceEvaluatePayload) -> None:
        if await self._repository.find_session(payload.session_id) is None:
            return
        await self._evaluation.generate(payload.session_id)

    async def mark_completed(self, payload: VoiceEvaluatePayload) -> None:
        await self._status_service.update_evaluate_status(
            payload.session_id,
            "COMPLETED",
            None,
        )

    async def retry(self, payload: VoiceEvaluatePayload, retry_count: int) -> None:
        try:
            await self._streams.add(
                VOICE_EVALUATE.key,
                {
                    FIELD_VOICE_SESSION_ID: str(payload.session_id),
                    FIELD_RETRY_COUNT: str(retry_count),
                },
            )
        except Exception as error:
            await self._status_service.update_evaluate_status(
                payload.session_id,
                "FAILED",
                f"重试入队失败: {error}"[:500],
            )
            raise

    async def mark_failed(
        self,
        payload: VoiceEvaluatePayload,
        error: str,
    ) -> None:
        if error.startswith("task failed after retry "):
            error = error.replace(
                "task failed after retry ",
                "语音面试评估 failed after retry ",
                1,
            )
        await self._status_service.update_evaluate_status(
            payload.session_id,
            "FAILED",
            error,
        )
