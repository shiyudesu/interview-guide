from __future__ import annotations

import asyncio
import logging
import re
import time
import unicodedata
from dataclasses import dataclass
from typing import Any

from interview_guide.common.ai.adapter import ProviderConfig
from interview_guide.common.ai.prompts import PromptRepository, PromptSanitizer
from interview_guide.common.ai.structured import StructuredOutputInvoker, structured_output_format
from interview_guide.common.config.settings import Settings
from interview_guide.common.db.models import InterviewQuestionRecord
from interview_guide.common.errors import ErrorCode
from interview_guide.modules.interview.models import (
    QuestionKind,
    TurnAction,
    TurnDecisionOutput,
    TurnDecisionStatus,
)
from interview_guide.modules.interview.question import InterviewSkillLibrary
from interview_guide.modules.interview.repository import SessionAggregate, parse_key_points

DECISION_OUTPUT_FORMAT = structured_output_format(
    {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["FOLLOW_UP", "NEXT_MAIN"]},
            "acknowledgement": {"type": "string"},
            "followUpQuestion": {"type": ["string", "null"]},
            "reasonCode": {"type": "string"},
            "reason": {"type": "string"},
            "targetTopic": {"type": ["string", "null"]},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        },
        "required": [
            "action",
            "acknowledgement",
            "followUpQuestion",
            "reasonCode",
            "reason",
            "targetTopic",
            "confidence",
        ],
        "additionalProperties": False,
    }
)
SKIP_ANSWERS = {"跳过", "换题", "skip", "pass"}
NORMALIZE_PATTERN = re.compile(r"[^\w\u4e00-\u9fff]+", re.UNICODE)
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TurnDecisionResult:
    action: TurnAction
    acknowledgement: str
    follow_up_question: str | None
    reason_code: str
    reason: str
    target_topic: str | None
    confidence: float | None
    status: TurnDecisionStatus
    provider_id: str | None
    model_name: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    duration_ms: int
    error: str | None


class InterviewTurnDecisionService:
    def __init__(
        self,
        structured: StructuredOutputInvoker,
        prompts: PromptRepository,
        sanitizer: PromptSanitizer,
        skills: InterviewSkillLibrary,
        settings: Settings,
    ) -> None:
        self._structured = structured
        self._prompts = prompts
        self._sanitizer = sanitizer
        self._skills = skills
        self._settings = settings

    async def decide(
        self,
        provider: ProviderConfig,
        aggregate: SessionAggregate,
        answer: str | None,
        *,
        remaining_seconds: int | None = None,
    ) -> TurnDecisionResult:
        started = time.monotonic()
        current = self._current_question(aggregate)
        has_next_main = any(
            question.kind == QuestionKind.MAIN.value
            and question.main_order > current.main_order
            for question in aggregate.questions
        )
        follow_ups = self._follow_ups(aggregate, current)
        deterministic = self._deterministic_decision(
            answer,
            has_next_main,
            len(follow_ups),
            aggregate.session.max_follow_ups_per_main,
            remaining_seconds,
        )
        if deterministic is not None:
            return deterministic
        try:
            system = (
                self._prompts.render("interview-turn-decision-system.st")
                + "\n\n"
                + DECISION_OUTPUT_FORMAT
            )
            user = self._prompts.render(
                "interview-turn-decision-user.st",
                self._context(aggregate, current, answer, follow_ups),
            )
            async with asyncio.timeout(
                self._settings.interview_turn_decision_timeout_seconds
            ):
                invocation = await self._structured.invoke_with_metadata(
                    provider,
                    system,
                    user,
                    TurnDecisionOutput,
                    ErrorCode.AI_SERVICE_ERROR,
                    "轮次决策失败：",
                )
            output = invocation.value
            usage = invocation.response.usage or {}
            action = output.action
            follow_up_question = output.follow_up_question
            if output.confidence < self._settings.interview_turn_confidence_threshold:
                action = TurnAction.NEXT_MAIN
                follow_up_question = None
            if action == TurnAction.FOLLOW_UP and self._duplicate_follow_up(
                follow_ups,
                follow_up_question,
                output.target_topic,
            ):
                action = TurnAction.NEXT_MAIN
                follow_up_question = None
            if action == TurnAction.NEXT_MAIN and not has_next_main:
                action = TurnAction.COMPLETE
            return TurnDecisionResult(
                action=action,
                acknowledgement=output.acknowledgement.strip(),
                follow_up_question=follow_up_question,
                reason_code=output.reason_code,
                reason=output.reason,
                target_topic=output.target_topic,
                confidence=output.confidence,
                status=TurnDecisionStatus.COMPLETED,
                provider_id=provider.provider_id,
                model_name=provider.model,
                prompt_tokens=self._usage_int(usage, "prompt_tokens"),
                completion_tokens=self._usage_int(usage, "completion_tokens"),
                total_tokens=self._usage_int(usage, "total_tokens"),
                duration_ms=int((time.monotonic() - started) * 1000),
                error=None,
            )
        except Exception as error:
            action = TurnAction.NEXT_MAIN if has_next_main else TurnAction.COMPLETE
            return TurnDecisionResult(
                action=action,
                acknowledgement=(
                    "好的，我们继续下一题。"
                    if action == TurnAction.NEXT_MAIN
                    else "好的，本次面试到这里。"
                ),
                follow_up_question=None,
                reason_code="MODEL_FALLBACK",
                reason="模型决策不可用，使用确定性回退",
                target_topic=None,
                confidence=None,
                status=TurnDecisionStatus.FALLBACK,
                provider_id=provider.provider_id,
                model_name=provider.model,
                prompt_tokens=None,
                completion_tokens=None,
                total_tokens=None,
                duration_ms=int((time.monotonic() - started) * 1000),
                error=str(error),
            )

    def fallback_for_stale(self, aggregate: SessionAggregate) -> TurnDecisionResult:
        return self.fallback_without_model(
            aggregate,
            reason_code="STALE_PROCESSING_RECOVERY",
            error="processing lease expired",
        )

    def fallback_without_model(
        self,
        aggregate: SessionAggregate,
        *,
        reason_code: str,
        error: str,
    ) -> TurnDecisionResult:
        current = self._current_question(aggregate)
        has_next = any(
            question.kind == QuestionKind.MAIN.value
            and question.main_order > current.main_order
            for question in aggregate.questions
        )
        action = TurnAction.NEXT_MAIN if has_next else TurnAction.COMPLETE
        return TurnDecisionResult(
            action=action,
            acknowledgement=(
                "好的，我们继续下一题。"
                if has_next
                else "好的，本次面试到这里。"
            ),
            follow_up_question=None,
            reason_code=reason_code,
            reason="决策模型不可用，使用确定性回退",
            target_topic=None,
            confidence=None,
            status=TurnDecisionStatus.FALLBACK,
            provider_id=None,
            model_name=None,
            prompt_tokens=None,
            completion_tokens=None,
            total_tokens=None,
            duration_ms=0,
            error=error,
        )

    def _deterministic_decision(
        self,
        answer: str | None,
        has_next_main: bool,
        follow_up_count: int,
        max_follow_ups: int,
        remaining_seconds: int | None,
    ) -> TurnDecisionResult | None:
        normalized = (answer or "").strip().lower()
        reason_code: str | None = None
        acknowledgement = "好的，我们继续下一题。"
        if not normalized:
            reason_code = "EMPTY_ANSWER"
        elif normalized in SKIP_ANSWERS:
            reason_code = "USER_SKIPPED"
            acknowledgement = "好的，我们换一道题。"
        elif follow_up_count >= max_follow_ups:
            reason_code = "FOLLOW_UP_LIMIT_REACHED"
        elif (
            remaining_seconds is not None
            and remaining_seconds < self._settings.voice_turn_min_remaining_seconds
        ):
            reason_code = "TIME_BUDGET_EXHAUSTED"
        if reason_code is None:
            return None
        action = TurnAction.NEXT_MAIN if has_next_main else TurnAction.COMPLETE
        if action == TurnAction.COMPLETE:
            acknowledgement = "好的，本次面试到这里。"
        return TurnDecisionResult(
            action=action,
            acknowledgement=acknowledgement,
            follow_up_question=None,
            reason_code=reason_code,
            reason="服务端确定性规则已决定轮次推进",
            target_topic=None,
            confidence=None,
            status=TurnDecisionStatus.COMPLETED,
            provider_id=None,
            model_name=None,
            prompt_tokens=None,
            completion_tokens=None,
            total_tokens=None,
            duration_ms=0,
            error=None,
        )

    def _context(
        self,
        aggregate: SessionAggregate,
        current: InterviewQuestionRecord,
        answer: str | None,
        follow_ups: list[InterviewQuestionRecord],
    ) -> dict[str, str]:
        turn_by_question = {turn.question_id: turn for turn in aggregate.turns}
        current_chain = []
        main = next(
            question
            for question in aggregate.questions
            if question.main_order == current.main_order
            and question.kind == QuestionKind.MAIN.value
        )
        for question in [main, *follow_ups]:
            turn = turn_by_question.get(question.id)
            current_chain.append(
                f"问题：{question.question}\n回答："
                f"{turn.answer if turn is not None and turn.answer is not None else '(未回答)'}"
            )
        recent: list[str] = []
        recent_turns = [
            turn
            for turn in aggregate.turns
            if turn.decision_status != TurnDecisionStatus.PROCESSING.value
        ][-self._settings.interview_turn_recent_count :]
        question_by_id = {question.id: question for question in aggregate.questions}
        for turn in recent_turns:
            recent_question = question_by_id.get(turn.question_id)
            if recent_question is not None:
                recent.append(
                    f"问：{recent_question.question}\n答：{turn.answer or '(未回答)'}"
                )
        context_parts = [f"渠道：{aggregate.session.channel}"]
        if aggregate.resume_text:
            context_parts.append(f"简历：{aggregate.resume_text}")
        if aggregate.session.context_json:
            context_parts.append(f"会话配置：{aggregate.session.context_json}")
        try:
            skill = self._skills.resolve(aggregate.session.skill_id or "java-backend", None, None)
            if skill.persona:
                context_parts.append(f"面试官角色：{skill.persona}")
        except Exception:
            logger.warning("failed to load interview skill context", exc_info=True)
        reference_parts = [
            current.reference_answer or "",
            "关键点：" + "、".join(parse_key_points(current.key_points_json)),
            current.scoring_rubric or "",
            current.source_context or "",
        ]
        values = {
            "currentQuestion": current.question,
            "currentAnswer": answer or "(未回答)",
            "currentChain": "\n\n".join(current_chain),
            "recentTurns": "\n\n".join(recent) or "无",
            "interviewContext": "\n\n".join(context_parts),
            "referenceContext": "\n\n".join(part for part in reference_parts if part) or "无",
        }
        remaining = self._settings.interview_turn_context_max_chars
        result: dict[str, str] = {}
        for key, value in values.items():
            limited = value[:remaining]
            remaining = max(0, remaining - len(limited))
            result[key] = self._sanitizer.wrap_with_delimiters(
                key,
                self._sanitizer.sanitize(limited) or "",
            )
        return result

    @staticmethod
    def _current_question(aggregate: SessionAggregate) -> InterviewQuestionRecord:
        current_id = aggregate.session.current_question_id
        return next(question for question in aggregate.questions if question.id == current_id)

    @staticmethod
    def _follow_ups(
        aggregate: SessionAggregate,
        current: InterviewQuestionRecord,
    ) -> list[InterviewQuestionRecord]:
        return [
            question
            for question in aggregate.questions
            if question.main_order == current.main_order
            and question.kind == QuestionKind.FOLLOW_UP.value
        ]

    @staticmethod
    def _duplicate_follow_up(
        existing: list[InterviewQuestionRecord],
        question: str | None,
        topic: str | None,
    ) -> bool:
        normalized_question = normalize_topic(question)
        normalized_topic = normalize_topic(topic)
        for item in existing:
            if normalized_question and normalize_topic(item.question) == normalized_question:
                return True
            if normalized_topic and normalize_topic(item.topic_summary) == normalized_topic:
                return True
        return False

    @staticmethod
    def _usage_int(usage: dict[str, Any], key: str) -> int | None:
        value = usage.get(key)
        return int(value) if isinstance(value, int | float) else None


def normalize_topic(value: str | None) -> str:
    if value is None:
        return ""
    normalized = unicodedata.normalize("NFKC", value).lower()
    return NORMALIZE_PATTERN.sub("", normalized)
