from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Protocol, TypeVar, cast

from redis.asyncio import Redis
from redis.exceptions import ResponseError

logger = logging.getLogger(__name__)

MAX_RETRY_COUNT = 3
BATCH_SIZE = 10
PENDING_IDLE_TIMEOUT_MS = 5 * 60 * 1000
PENDING_CLAIM_BATCH_SIZE = 10
POLL_INTERVAL_MS = 1000
STREAM_MAX_LEN = 1000
FIELD_RETRY_COUNT = "retryCount"
FIELD_CONTENT = "content"
FIELD_KB_ID = "kbId"
FIELD_RESUME_ID = "resumeId"
FIELD_SESSION_ID = "sessionId"
FIELD_VOICE_SESSION_ID = "voiceSessionId"
FIELD_TASK_ID = "taskId"
FIELD_DIFFICULTY = "difficulty"
FIELD_QUESTION_COUNT = "questionCount"
FIELD_FOLLOW_UP_COUNT = "followUpCount"
FIELD_CATEGORY_LIMIT = "categoryLimit"
FIELD_LLM_PROVIDER = "llmProvider"


@dataclass(frozen=True)
class StreamDefinition:
    key: str
    group: str
    consumer_prefix: str


KB_VECTORIZE = StreamDefinition(
    "knowledgebase:vectorize:stream",
    "vectorize-group",
    "vectorize-consumer-",
)
RESUME_ANALYZE = StreamDefinition(
    "resume:analyze:stream",
    "analyze-group",
    "analyze-consumer-",
)
INTERVIEW_EVALUATE = StreamDefinition(
    "interview:evaluate:stream",
    "evaluate-group",
    "evaluate-consumer-",
)
VOICE_EVALUATE = StreamDefinition(
    "voice:evaluate:stream",
    "voice-evaluate-group",
    "voice-evaluate-consumer-",
)
KB_QUESTION_GEN = StreamDefinition(
    "knowledgebase:question-gen:stream",
    "question-gen-group",
    "question-gen-consumer-",
)
STREAM_DEFINITIONS = (
    KB_VECTORIZE,
    RESUME_ANALYZE,
    INTERVIEW_EVALUATE,
    VOICE_EVALUATE,
    KB_QUESTION_GEN,
)


@dataclass(frozen=True)
class StreamMessage:
    message_id: str
    data: dict[str, str]

    @property
    def retry_count(self) -> int:
        try:
            return int(self.data.get(FIELD_RETRY_COUNT, "0"))
        except ValueError:
            return 0


class RedisStreamService:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis
        self._reclaim_cursors: dict[tuple[str, str], str] = {}

    async def ensure_group(self, definition: StreamDefinition) -> None:
        try:
            await self._redis.xgroup_create(
                definition.key,
                definition.group,
                id="0-0",
                mkstream=True,
            )
        except ResponseError as error:
            if "BUSYGROUP" not in str(error):
                raise

    async def add(
        self,
        stream_key: str,
        fields: dict[str, str],
        *,
        max_len: int = STREAM_MAX_LEN,
        message_id: str = "*",
    ) -> str:
        result = await self._redis.xadd(
            stream_key,
            cast(dict[Any, Any], fields),
            id=message_id,
            maxlen=max_len if max_len > 0 else None,
            approximate=True,
        )
        return str(result)

    async def read_batch(
        self,
        definition: StreamDefinition,
        consumer_name: str,
        *,
        count: int = BATCH_SIZE,
        block_ms: int = POLL_INTERVAL_MS,
        pending_idle_ms: int = PENDING_IDLE_TIMEOUT_MS,
        claim_count: int = PENDING_CLAIM_BATCH_SIZE,
    ) -> list[StreamMessage]:
        reclaimed = await self._reclaim(
            definition,
            consumer_name,
            pending_idle_ms=pending_idle_ms,
            count=claim_count,
        )
        if reclaimed:
            return reclaimed
        response = await self._redis.xreadgroup(
            definition.group,
            consumer_name,
            streams={definition.key: ">"},
            count=count,
            block=block_ms,
        )
        return self._decode_read_response(response)

    async def _reclaim(
        self,
        definition: StreamDefinition,
        consumer_name: str,
        *,
        pending_idle_ms: int,
        count: int,
    ) -> list[StreamMessage]:
        if pending_idle_ms <= 0 or count <= 0:
            return []
        cursor_key = (definition.key, definition.group)
        start_id = self._reclaim_cursors.get(cursor_key, "0-0")
        response = await self._redis.xautoclaim(
            definition.key,
            definition.group,
            consumer_name,
            min_idle_time=pending_idle_ms,
            start_id=start_id,
            count=count,
        )
        next_id = str(response[0])
        if next_id == "0-0":
            self._reclaim_cursors.pop(cursor_key, None)
        else:
            self._reclaim_cursors[cursor_key] = next_id
        raw_messages = cast(list[tuple[str, dict[str, str]]], response[1])
        if raw_messages:
            logger.info(
                "reclaimed stream messages stream=%s group=%s consumer=%s count=%s",
                definition.key,
                definition.group,
                consumer_name,
                len(raw_messages),
            )
        return [
            StreamMessage(message_id=str(message_id), data=dict(fields))
            for message_id, fields in raw_messages
        ]

    @staticmethod
    def _decode_read_response(response: Any) -> list[StreamMessage]:
        if not response:
            return []
        messages: list[StreamMessage] = []
        for _, raw_messages in cast(
            list[tuple[str, list[tuple[str, dict[str, str]]]]],
            response,
        ):
            messages.extend(
                StreamMessage(message_id=str(message_id), data=dict(fields))
                for message_id, fields in raw_messages
            )
        return messages

    async def ack(
        self,
        definition: StreamDefinition,
        *message_ids: str,
    ) -> int:
        if not message_ids:
            return 0
        return int(
            await self._redis.xack(
                definition.key,
                definition.group,
                *message_ids,
            )
        )


T = TypeVar("T")


class StreamHandler(Protocol[T]):
    async def parse(self, message: StreamMessage) -> T | None: ...

    async def should_skip(self, payload: T) -> bool: ...

    async def try_mark_processing(self, payload: T) -> bool: ...

    async def process(self, payload: T) -> None: ...

    async def mark_completed(self, payload: T) -> None: ...

    async def retry(self, payload: T, retry_count: int) -> None: ...

    async def mark_failed(self, payload: T, error: str) -> None: ...


class SequentialStreamConsumer[T]:
    def __init__(
        self,
        streams: RedisStreamService,
        definition: StreamDefinition,
        consumer_name: str,
        handler: StreamHandler[T],
    ) -> None:
        self._streams = streams
        self._definition = definition
        self._consumer_name = consumer_name
        self._handler = handler

    async def process_message(self, message: StreamMessage) -> None:
        try:
            payload = await self._handler.parse(message)
        except Exception:
            logger.warning(
                "failed to parse stream message; ack and discard stream=%s id=%s",
                self._definition.key,
                message.message_id,
                exc_info=True,
            )
            await self._streams.ack(self._definition, message.message_id)
            return
        if payload is None:
            await self._streams.ack(self._definition, message.message_id)
            return
        if await self._handler.should_skip(payload):
            await self._streams.ack(self._definition, message.message_id)
            return
        if not await self._handler.try_mark_processing(payload):
            await self._streams.ack(self._definition, message.message_id)
            return
        try:
            await self._handler.process(payload)
            await self._handler.mark_completed(payload)
        except Exception as error:
            retry_count = message.retry_count
            if retry_count < MAX_RETRY_COUNT:
                await self._handler.retry(payload, retry_count + 1)
            else:
                detail = f"task failed after retry {retry_count}: {error}"
                await self._handler.mark_failed(payload, detail[:500])
        await self._streams.ack(self._definition, message.message_id)

    async def run(self, stop_event: asyncio.Event) -> None:
        await self._streams.ensure_group(self._definition)
        while not stop_event.is_set():
            messages = await self._streams.read_batch(
                self._definition,
                self._consumer_name,
            )
            for message in messages:
                await self.process_message(message)


async def run_stream_consumers(
    consumers: tuple[SequentialStreamConsumer[Any], ...],
    stop_event: asyncio.Event,
) -> None:
    async with asyncio.TaskGroup() as task_group:
        for consumer in consumers:
            task_group.create_task(consumer.run(stop_event))
