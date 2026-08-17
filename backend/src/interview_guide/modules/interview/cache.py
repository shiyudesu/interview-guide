from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar, cast

from redis.asyncio import Redis

from interview_guide.common.api.models import compact_json_text
from interview_guide.common.errors import BusinessException, ErrorCode
from interview_guide.modules.interview.models import (
    InterviewQuestion,
    InterviewSessionStatus,
)

SESSION_KEY_PREFIX = "interview:session:"
RESUME_SESSION_KEY_PREFIX = "interview:resume:"
CREATE_LOCK_PREFIX = "interview:create:"
CREATE_RESULT_PREFIX = "interview:create:result:"
SESSION_TTL_SECONDS = 24 * 60 * 60
CREATE_RESULT_TTL_SECONDS = 24 * 60 * 60
CREATE_LOCK_WAIT_SECONDS = 185
CREATE_LOCK_LEASE_SECONDS = 600
LOCK_RELEASE_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('del', KEYS[1])
end
return 0
"""

T = TypeVar("T")


@dataclass
class CachedSession:
    session_id: str
    resume_text: str
    resume_id: int | None
    knowledge_base_id: int | None
    interview_category: str | None
    questions_json: str
    current_index: int
    status: InterviewSessionStatus

    @property
    def questions(self) -> list[InterviewQuestion]:
        value = json.loads(self.questions_json)
        return [InterviewQuestion.model_validate(item) for item in value]

    def document(self) -> dict[str, object]:
        return {
            "sessionId": self.session_id,
            "resumeText": self.resume_text,
            "resumeId": self.resume_id,
            "knowledgeBaseId": self.knowledge_base_id,
            "interviewCategory": self.interview_category,
            "questionsJson": self.questions_json,
            "currentIndex": self.current_index,
            "status": self.status.value,
        }

    @classmethod
    def from_document(cls, value: dict[str, object]) -> CachedSession:
        return cls(
            session_id=str(value["sessionId"]),
            resume_text=str(value.get("resumeText") or ""),
            resume_id=cast(int | None, value.get("resumeId")),
            knowledge_base_id=cast(int | None, value.get("knowledgeBaseId")),
            interview_category=cast(str | None, value.get("interviewCategory")),
            questions_json=str(value["questionsJson"]),
            current_index=int(cast(int, value["currentIndex"])),
            status=InterviewSessionStatus(str(value["status"])),
        )


class InterviewSessionCache:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def save_session(
        self,
        session_id: str,
        resume_text: str,
        resume_id: int | None,
        knowledge_base_id: int | None,
        interview_category: str | None,
        questions: list[InterviewQuestion],
        current_index: int,
        status: InterviewSessionStatus,
    ) -> None:
        cached = CachedSession(
            session_id=session_id,
            resume_text=resume_text,
            resume_id=resume_id,
            knowledge_base_id=knowledge_base_id,
            interview_category=interview_category,
            questions_json=compact_json_text(
                [item.model_dump(by_alias=True) for item in questions]
            ),
            current_index=current_index,
            status=status,
        )
        await self._redis.set(
            f"{SESSION_KEY_PREFIX}{session_id}",
            compact_json_text(cached.document()),
            ex=SESSION_TTL_SECONDS,
        )
        if resume_id is not None and self._unfinished(status):
            await self._redis.set(
                f"{RESUME_SESSION_KEY_PREFIX}{resume_id}",
                session_id,
                ex=SESSION_TTL_SECONDS,
            )

    async def get_session(self, session_id: str) -> CachedSession | None:
        raw = await self._redis.get(f"{SESSION_KEY_PREFIX}{session_id}")
        if raw is None:
            return None
        document = json.loads(str(raw))
        return CachedSession.from_document(document)

    async def update_status(
        self,
        session_id: str,
        status: InterviewSessionStatus,
    ) -> None:
        cached = await self.get_session(session_id)
        if cached is None:
            return
        cached.status = status
        await self._redis.set(
            f"{SESSION_KEY_PREFIX}{session_id}",
            compact_json_text(cached.document()),
            ex=SESSION_TTL_SECONDS,
        )
        if not self._unfinished(status) and cached.resume_id is not None:
            await self._remove_resume_mapping(cached.resume_id, session_id)

    async def update_current_index(self, session_id: str, current_index: int) -> None:
        cached = await self.get_session(session_id)
        if cached is None:
            return
        cached.current_index = current_index
        await self._redis.set(
            f"{SESSION_KEY_PREFIX}{session_id}",
            compact_json_text(cached.document()),
            ex=SESSION_TTL_SECONDS,
        )

    async def update_questions(
        self,
        session_id: str,
        questions: list[InterviewQuestion],
    ) -> None:
        cached = await self.get_session(session_id)
        if cached is None:
            return
        cached.questions_json = compact_json_text(
            [item.model_dump(by_alias=True) for item in questions]
        )
        await self._redis.set(
            f"{SESSION_KEY_PREFIX}{session_id}",
            compact_json_text(cached.document()),
            ex=SESSION_TTL_SECONDS,
        )

    async def find_unfinished_session_id(self, resume_id: int) -> str | None:
        key = f"{RESUME_SESSION_KEY_PREFIX}{resume_id}"
        session_id = await self._redis.get(key)
        if session_id is None:
            return None
        cached = await self.get_session(str(session_id))
        if cached is not None and self._unfinished(cached.status):
            return str(session_id)
        await self._redis.delete(key)
        return None

    async def refresh_session_ttl(self, session_id: str) -> None:
        await self._redis.expire(
            f"{SESSION_KEY_PREFIX}{session_id}",
            SESSION_TTL_SECONDS,
        )

    async def get_create_result(self, request_id: str) -> str | None:
        value = await self._redis.get(f"{CREATE_RESULT_PREFIX}{request_id}")
        return str(value) if value is not None else None

    async def set_create_result(self, request_id: str, session_id: str) -> None:
        await self._redis.set(
            f"{CREATE_RESULT_PREFIX}{request_id}",
            session_id,
            ex=CREATE_RESULT_TTL_SECONDS,
        )

    async def execute_create_locked(
        self,
        request_id: str,
        operation: Callable[[], Awaitable[T]],
    ) -> T:
        key = f"{CREATE_LOCK_PREFIX}{request_id}"
        owner = uuid.uuid4().hex
        deadline = time.monotonic() + CREATE_LOCK_WAIT_SECONDS
        acquired = False
        while time.monotonic() < deadline:
            acquired = bool(
                await self._redis.set(
                    key,
                    owner,
                    nx=True,
                    ex=CREATE_LOCK_LEASE_SECONDS,
                )
            )
            if acquired:
                break
            await asyncio.sleep(0.1)
        if not acquired:
            raise BusinessException(ErrorCode.INTERNAL_ERROR, f"获取锁失败: {key}")
        try:
            return await operation()
        finally:
            await self._redis.eval(LOCK_RELEASE_SCRIPT, 1, key, owner)

    async def _remove_resume_mapping(self, resume_id: int, session_id: str) -> None:
        key = f"{RESUME_SESSION_KEY_PREFIX}{resume_id}"
        current = await self._redis.get(key)
        if current == session_id:
            await self._redis.delete(key)

    @staticmethod
    def _unfinished(status: InterviewSessionStatus) -> bool:
        return status in {
            InterviewSessionStatus.CREATED,
            InterviewSessionStatus.IN_PROGRESS,
        }
