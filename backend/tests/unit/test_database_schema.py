from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from types import ModuleType

from pgvector.sqlalchemy import Vector

from interview_guide.common.db.base import Base
from interview_guide.common.db.models import (
    InterviewSchedule,
    KnowledgeBase,
    VectorStore,
)

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def load_initial_revision() -> ModuleType:
    revision_path = BACKEND_ROOT / "alembic/versions/0001_initial_schema.py"
    spec = importlib.util.spec_from_file_location(
        "initial_schema_revision",
        revision_path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {revision_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_revision(name: str) -> ModuleType:
    revision_path = BACKEND_ROOT / f"alembic/versions/{name}.py"
    spec = importlib.util.spec_from_file_location(name, revision_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {revision_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_initial_sql_splitter_preserves_do_blocks() -> None:
    revision = load_initial_revision()
    document = (BACKEND_ROOT / "alembic/sql/0001_initial_schema.sql").read_text(encoding="utf-8")

    statements = revision.split_sql_statements(document)

    assert len(statements) == 39
    assert any(
        "-- BEGIN V20260722" in statement and "DO $$" in statement for statement in statements
    )
    assert any("CHECK (question_gen_status IN" in statement for statement in statements)


def test_sqlalchemy_metadata_contains_all_business_tables() -> None:
    assert set(Base.metadata.tables) == {
        "interview_questions",
        "interview_schedule",
        "interview_sessions",
        "interview_turns",
        "knowledge_base_questions",
        "knowledge_bases",
        "llm_global_setting",
        "llm_provider_config",
        "rag_chat_messages",
        "rag_chat_sessions",
        "rag_session_knowledge_bases",
        "resume_analyses",
        "resumes",
        "vector_store",
        "voice_interview_messages",
        "voice_interview_sessions",
    }


def test_identity_vector_and_added_columns_match_schema() -> None:
    identity = InterviewSchedule.__table__.c.id.identity
    assert identity is not None
    assert identity.always is False

    vector_type = VectorStore.__table__.c.embedding.type
    assert isinstance(vector_type, Vector)
    assert vector_type.dim == 1024

    knowledge_base_columns = KnowledgeBase.__table__.c
    assert knowledge_base_columns.question_gen_status.server_default is not None
    assert knowledge_base_columns.question_gen_saved_count.nullable is False


def test_destructive_interview_migration_requires_explicit_guard() -> None:
    revision = load_revision("0004_contract_adaptive_interview")
    previous = os.environ.pop(revision.RESET_ENV, None)
    try:
        try:
            revision.upgrade()
        except RuntimeError as error:
            assert revision.RESET_ENV in str(error)
        else:
            raise AssertionError("destructive migration should require an explicit guard")
    finally:
        if previous is not None:
            os.environ[revision.RESET_ENV] = previous
