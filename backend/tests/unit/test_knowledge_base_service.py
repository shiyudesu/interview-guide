from __future__ import annotations

from dataclasses import dataclass

import pytest

from interview_guide.modules.knowledge_base.repository import java_trim
from interview_guide.modules.knowledge_base.service import (
    KnowledgeBaseService,
    java_is_blank,
    java_string_length,
)


def test_java_string_length_counts_utf16_code_units() -> None:
    assert java_string_length("知识库😀") == 5


def test_java_blank_and_trim_compatibility() -> None:
    assert java_trim("\t fixed \n") == "fixed"
    assert java_is_blank("") is True
    assert java_is_blank(" \t\n") is True
    assert java_is_blank(" value ") is False


@dataclass
class RecordingStorage:
    events: list[str]
    fail: bool = False

    async def delete(self, key: str | None) -> None:
        self.events.append(f"storage:{key}")
        if self.fail:
            raise RuntimeError("storage failure")


class DeleteOrderProbe(KnowledgeBaseService):
    def __init__(
        self,
        events: list[str],
        storage: RecordingStorage,
        *,
        vector_failure: bool = False,
    ) -> None:
        self._events = events
        self._storage = storage
        self._vector_failure = vector_failure

    async def _delete_database_records(
        self,
        knowledge_base_id: int,
    ) -> str | None:
        self._events.append(f"database:{knowledge_base_id}")
        return "knowledgebases/fixed.txt"

    async def _delete_vectors(self, knowledge_base_id: int) -> None:
        self._events.append(f"vector:{knowledge_base_id}")
        if self._vector_failure:
            raise RuntimeError("vector failure")


@pytest.mark.asyncio
async def test_delete_order_is_database_then_vector_then_storage() -> None:
    events: list[str] = []
    service = DeleteOrderProbe(events, RecordingStorage(events))

    await service.delete(7)

    assert events == [
        "database:7",
        "vector:7",
        "storage:knowledgebases/fixed.txt",
    ]


@pytest.mark.asyncio
async def test_delete_continues_after_vector_and_storage_cleanup_failures() -> None:
    events: list[str] = []
    service = DeleteOrderProbe(
        events,
        RecordingStorage(events, fail=True),
        vector_failure=True,
    )

    await service.delete(8)

    assert events == [
        "database:8",
        "vector:8",
        "storage:knowledgebases/fixed.txt",
    ]
