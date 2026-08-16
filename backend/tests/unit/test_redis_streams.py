from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from interview_guide.common.redis.streams import (
    MAX_RETRY_COUNT,
    RESUME_ANALYZE,
    SequentialStreamConsumer,
    StreamMessage,
)


@dataclass
class FakeStreams:
    events: list[str] = field(default_factory=list)

    async def ack(self, definition: object, *message_ids: str) -> int:
        del definition
        self.events.append(f"ack:{','.join(message_ids)}")
        return len(message_ids)


@dataclass
class Handler:
    events: list[str]
    fail: bool = False
    parse_error: bool = False

    async def parse(self, message: StreamMessage) -> str | None:
        self.events.append("parse")
        if self.parse_error:
            raise ValueError("invalid payload")
        return message.data.get("resumeId")

    async def should_skip(self, payload: str) -> bool:
        self.events.append(f"skip:{payload}")
        return False

    async def try_mark_processing(self, payload: str) -> bool:
        self.events.append(f"mark-processing:{payload}")
        return True

    async def process(self, payload: str) -> None:
        self.events.append(f"process:{payload}")
        if self.fail:
            raise RuntimeError("provider failed")

    async def mark_completed(self, payload: str) -> None:
        self.events.append(f"completed:{payload}")

    async def retry(self, payload: str, retry_count: int) -> None:
        self.events.append(f"retry:{payload}:{retry_count}")

    async def mark_failed(self, payload: str, error: str) -> None:
        self.events.append(f"failed:{payload}:{error}")


@pytest.mark.asyncio
async def test_success_ack_occurs_after_completion() -> None:
    streams = FakeStreams()
    handler = Handler(streams.events)
    consumer = SequentialStreamConsumer(
        streams,  # type: ignore[arg-type]
        RESUME_ANALYZE,
        "analyze-consumer-test",
        handler,
    )

    await consumer.process_message(StreamMessage("1-0", {"resumeId": "7", "retryCount": "0"}))

    assert streams.events == [
        "parse",
        "skip:7",
        "mark-processing:7",
        "process:7",
        "completed:7",
        "ack:1-0",
    ]


@pytest.mark.asyncio
async def test_failure_requeues_before_ack() -> None:
    streams = FakeStreams()
    handler = Handler(streams.events, fail=True)
    consumer = SequentialStreamConsumer(
        streams,  # type: ignore[arg-type]
        RESUME_ANALYZE,
        "analyze-consumer-test",
        handler,
    )

    await consumer.process_message(StreamMessage("2-0", {"resumeId": "8", "retryCount": "1"}))

    assert streams.events[-2:] == ["retry:8:2", "ack:2-0"]


@pytest.mark.asyncio
async def test_final_failure_is_saved_before_ack() -> None:
    streams = FakeStreams()
    handler = Handler(streams.events, fail=True)
    consumer = SequentialStreamConsumer(
        streams,  # type: ignore[arg-type]
        RESUME_ANALYZE,
        "analyze-consumer-test",
        handler,
    )

    await consumer.process_message(
        StreamMessage(
            "3-0",
            {"resumeId": "9", "retryCount": str(MAX_RETRY_COUNT)},
        )
    )

    assert streams.events[-2].startswith("failed:9:task failed after retry 3: provider failed")
    assert streams.events[-1] == "ack:3-0"


@pytest.mark.asyncio
async def test_parse_error_is_acked_and_discarded() -> None:
    streams = FakeStreams()
    handler = Handler(streams.events, parse_error=True)
    consumer = SequentialStreamConsumer(
        streams,  # type: ignore[arg-type]
        RESUME_ANALYZE,
        "analyze-consumer-test",
        handler,
    )

    await consumer.process_message(StreamMessage("4-0", {"invalid": "payload"}))

    assert streams.events == ["parse", "ack:4-0"]
