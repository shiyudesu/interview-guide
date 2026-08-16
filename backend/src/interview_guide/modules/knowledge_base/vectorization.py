from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

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
