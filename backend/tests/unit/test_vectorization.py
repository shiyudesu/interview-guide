from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

import pytest

from interview_guide.common.ai.adapter import ProviderConfig
from interview_guide.common.errors import BusinessException
from interview_guide.modules.knowledge_base.vectorization import (
    EMBEDDING_DIMENSIONS,
    EmbeddedVector,
    KnowledgeBaseVectorizationService,
    embedding_batches,
    pending_vectors,
    split_text,
)


def test_embedding_batches_never_exceed_ten() -> None:
    batches = embedding_batches(list(range(23)))
    assert [len(batch) for batch in batches] == [10, 10, 3]


def test_pending_metadata_is_not_promoted_early() -> None:
    vectors = pending_vectors(7, "fixed-job", ["a", "b"])
    assert vectors[0].metadata == {
        "kb_id": "pending:7:fixed-job",
        "kb_target_id": "7",
        "kb_vector_job_id": "fixed-job",
    }


def test_split_text_preserves_order() -> None:
    assert split_text("first\n\nsecond\n\nthird") == [
        "first\n\nsecond\n\nthird",
    ]


def test_split_text_matches_compatibility_minimum_chunk_length() -> None:
    assert split_text("short") == []


def test_split_text_matches_compatibility_cl100k_chunks() -> None:
    assert split_text(
        "one two three four five six seven eight nine ten eleven",
        chunk_size=3,
        min_chunk_size_characters=0,
        min_chunk_length_to_embed=0,
        max_num_chunks=100,
    ) == [
        "one two three",
        "four five six",
        "seven eight nine",
        "ten eleven",
    ]
    assert split_text(
        "😀 alpha. beta gamma! delta epsilon? zeta",
        chunk_size=3,
        min_chunk_size_characters=0,
        min_chunk_length_to_embed=0,
        max_num_chunks=100,
    ) == [
        "😀 alpha",
        ". beta gamma",
        "! delta epsilon",
        "? zeta",
    ]


@dataclass
class FakeVectorRepository:
    stored_batches: list[list[EmbeddedVector]] = field(default_factory=list)
    completed: list[tuple[int, str, int]] = field(default_factory=list)
    cleaned_jobs: list[str] = field(default_factory=list)

    async def store_pending_batch(self, vectors: Sequence[EmbeddedVector]) -> None:
        self.stored_batches.append(list(vectors))

    async def complete_job(
        self,
        knowledge_base_id: int,
        job_id: str,
        chunk_count: int,
    ) -> bool:
        self.completed.append((knowledge_base_id, job_id, chunk_count))
        return True

    async def cleanup_job(self, job_id: str) -> None:
        self.cleaned_jobs.append(job_id)


@dataclass
class FakeEmbeddingProviderRegistry:
    calls: int = 0

    async def get_embedding(
        self,
        provider_id: str | None = None,
    ) -> ProviderConfig:
        assert provider_id is None
        self.calls += 1
        return ProviderConfig(
            provider_id="fake-embedding-provider",
            base_url="http://fake.invalid/v1",
            api_key="fake-key",
            model="fake-chat",
            embedding_model="fake-embedding",
            embedding_dimensions=EMBEDDING_DIMENSIONS,
            supports_embedding=True,
        )


@dataclass
class FakeEmbeddingLlmAdapter:
    fail_on_call: int | None = None
    dimensions: int = EMBEDDING_DIMENSIONS
    batch_sizes: list[int] = field(default_factory=list)

    async def embed(
        self,
        provider: ProviderConfig,
        inputs: Sequence[str],
    ) -> list[list[float]]:
        assert provider.provider_id == "fake-embedding-provider"
        self.batch_sizes.append(len(inputs))
        if self.fail_on_call == len(self.batch_sizes):
            raise RuntimeError("fake embedding failure")
        return [[float(index)] * self.dimensions for index, _ in enumerate(inputs)]


def vectorization_service(
    repository: FakeVectorRepository,
    registry: FakeEmbeddingProviderRegistry,
    adapter: FakeEmbeddingLlmAdapter,
) -> KnowledgeBaseVectorizationService:
    return KnowledgeBaseVectorizationService(
        repository,
        registry,
        adapter,
        job_id_factory=lambda: "fixed-job",
        chunk_size=1,
        min_chunk_size_characters=0,
        min_chunk_length_to_embed=0,
    )


@pytest.mark.asyncio
async def test_fake_embedding_uses_default_provider_and_batches_sequentially() -> None:
    repository = FakeVectorRepository()
    registry = FakeEmbeddingProviderRegistry()
    adapter = FakeEmbeddingLlmAdapter()

    await vectorization_service(repository, registry, adapter).vectorize(
        7,
        "one two three four five six seven eight nine ten eleven",
    )

    assert registry.calls == 1
    assert adapter.batch_sizes == [10, 1]
    assert [len(batch) for batch in repository.stored_batches] == [10, 1]
    assert repository.stored_batches[0][0].metadata == {
        "kb_id": "pending:7:fixed-job",
        "kb_target_id": "7",
        "kb_vector_job_id": "fixed-job",
    }
    assert repository.completed == [(7, "fixed-job", 11)]
    assert repository.cleaned_jobs == []


@pytest.mark.asyncio
async def test_fake_embedding_failure_cleans_current_pending_job() -> None:
    repository = FakeVectorRepository()
    registry = FakeEmbeddingProviderRegistry()
    adapter = FakeEmbeddingLlmAdapter(fail_on_call=2)

    with pytest.raises(BusinessException, match="向量化知识库失败"):
        await vectorization_service(repository, registry, adapter).vectorize(
            8,
            "one two three four five six seven eight nine ten eleven",
        )

    assert [len(batch) for batch in repository.stored_batches] == [10]
    assert repository.completed == []
    assert repository.cleaned_jobs == ["fixed-job"]


@pytest.mark.asyncio
async def test_fake_embedding_wrong_dimension_is_rejected_and_cleaned() -> None:
    repository = FakeVectorRepository()
    registry = FakeEmbeddingProviderRegistry()
    adapter = FakeEmbeddingLlmAdapter(dimensions=EMBEDDING_DIMENSIONS - 1)

    with pytest.raises(BusinessException, match="Embedding dimension mismatch"):
        await vectorization_service(repository, registry, adapter).vectorize(9, "a")

    assert repository.stored_batches == []
    assert repository.completed == []
    assert repository.cleaned_jobs == ["fixed-job"]
