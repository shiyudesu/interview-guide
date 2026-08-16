from interview_guide.modules.knowledge_base.vectorization import (
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
        "kb_id": "pending:fixed-job",
        "kb_target_id": "7",
        "kb_vector_job_id": "fixed-job",
    }


def test_split_text_preserves_order() -> None:
    assert split_text("first\n\nsecond\n\nthird", max_characters=12) == [
        "first",
        "second",
        "third",
    ]
