from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from interview_guide.common.db.models import VectorStore

MAX_EMBEDDING_BATCH_SIZE = 10


@dataclass(frozen=True)
class PendingVector:
    content: str
    metadata: dict[str, str]


def split_text(content: str, max_characters: int = 2400) -> list[str]:
    paragraphs = [value.strip() for value in content.split("\n\n") if value.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}" if current else paragraph
        if len(candidate) <= max_characters:
            current = candidate
            continue
        if current:
            chunks.append(current)
        while len(paragraph) > max_characters:
            chunks.append(paragraph[:max_characters])
            paragraph = paragraph[max_characters:]
        current = paragraph
    if current:
        chunks.append(current)
    return chunks


def pending_vectors(
    knowledge_base_id: int,
    job_id: str,
    chunks: Iterable[str],
) -> list[PendingVector]:
    return [
        PendingVector(
            content=chunk,
            metadata={
                "kb_id": f"pending:{job_id}",
                "kb_target_id": str(knowledge_base_id),
                "kb_vector_job_id": job_id,
            },
        )
        for chunk in chunks
    ]


def embedding_batches[T](values: list[T]) -> list[list[T]]:
    return [
        values[index : index + MAX_EMBEDDING_BATCH_SIZE]
        for index in range(0, len(values), MAX_EMBEDDING_BATCH_SIZE)
    ]


async def promote_vector_job(
    session: AsyncSession,
    knowledge_base_id: int,
    job_id: str,
) -> None:
    target = str(knowledge_base_id)
    pending = f"pending:{job_id}"
    await session.execute(
        delete(VectorStore).where(
            VectorStore.metadata_json["kb_id"].astext == target
        )
    )
    await session.execute(
        update(VectorStore)
        .where(
            VectorStore.metadata_json["kb_id"].astext == pending,
            VectorStore.metadata_json["kb_vector_job_id"].astext == job_id,
        )
        .values(
            metadata_json=VectorStore.metadata_json.op("-")(
                "kb_target_id"
            ).op("-")("kb_vector_job_id").op("||")({"kb_id": target})
        )
    )
    await session.execute(
        delete(VectorStore).where(
            VectorStore.metadata_json["kb_target_id"].astext == target
        )
    )
