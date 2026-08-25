"""Scope idempotency, file hashes, and async Provider snapshots.

Revision ID: 0004_scope_async_and_files
Revises: 0003_add_user_providers
Create Date: 2026-08-25
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_scope_async_and_files"
down_revision: str | Sequence[str] | None = "0003_add_user_providers"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "resumes",
        sa.Column(
            "analysis_provider_alias",
            sa.String(length=64),
            nullable=False,
            server_default="dashscope",
        ),
    )
    op.add_column(
        "knowledge_bases",
        sa.Column(
            "embedding_provider_alias",
            sa.String(length=64),
            nullable=False,
            server_default="dashscope",
        ),
    )
    op.add_column(
        "knowledge_bases",
        sa.Column(
            "question_provider_alias",
            sa.String(length=64),
            nullable=False,
            server_default="dashscope",
        ),
    )
    op.execute(
        """
        UPDATE resumes AS resume
        SET analysis_provider_alias = provider.alias
        FROM user_ai_settings AS setting
        JOIN user_llm_providers AS provider
          ON provider.id = setting.default_chat_provider_id
        WHERE setting.user_id = resume.user_id
        """
    )
    op.execute(
        """
        UPDATE knowledge_bases AS knowledge_base
        SET embedding_provider_alias = embedding.alias,
            question_provider_alias = chat.alias
        FROM user_ai_settings AS setting
        JOIN user_llm_providers AS embedding
          ON embedding.id = setting.default_embedding_provider_id
        JOIN user_llm_providers AS chat
          ON chat.id = setting.default_chat_provider_id
        WHERE setting.user_id = knowledge_base.user_id
        """
    )
    op.drop_constraint("idx_resume_hash", "resumes", type_="unique")
    op.create_unique_constraint(
        "uq_resumes_user_hash",
        "resumes",
        ["user_id", "file_hash"],
    )
    op.drop_constraint("idx_kb_hash", "knowledge_bases", type_="unique")
    op.create_unique_constraint(
        "uq_knowledge_bases_user_hash",
        "knowledge_bases",
        ["user_id", "file_hash"],
    )
    op.drop_index("uk_interview_sessions_request_id", table_name="interview_sessions")
    op.create_index(
        "uk_interview_sessions_request_id",
        "interview_sessions",
        ["user_id", "request_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uk_interview_sessions_request_id", table_name="interview_sessions")
    op.create_index(
        "uk_interview_sessions_request_id",
        "interview_sessions",
        ["request_id"],
        unique=True,
    )
    op.drop_constraint(
        "uq_knowledge_bases_user_hash",
        "knowledge_bases",
        type_="unique",
    )
    op.create_unique_constraint("idx_kb_hash", "knowledge_bases", ["file_hash"])
    op.drop_constraint("uq_resumes_user_hash", "resumes", type_="unique")
    op.create_unique_constraint("idx_resume_hash", "resumes", ["file_hash"])
    op.drop_column("knowledge_bases", "question_provider_alias")
    op.drop_column("knowledge_bases", "embedding_provider_alias")
    op.drop_column("resumes", "analysis_provider_alias")
