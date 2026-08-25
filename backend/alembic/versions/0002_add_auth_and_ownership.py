"""Add authentication principals and legacy resource ownership.

Revision ID: 0002_add_auth_and_ownership
Revises: 0001_initial_schema
Create Date: 2026-08-25
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002_add_auth_and_ownership"
down_revision: str | Sequence[str] | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEGACY_OWNER_ID = "00000000-0000-0000-0000-000000000001"
OWNED_TABLES = (
    "interview_schedule",
    "resumes",
    "interview_sessions",
    "knowledge_bases",
    "rag_chat_sessions",
)


def upgrade() -> None:
    timestamp = postgresql.TIMESTAMP(timezone=False, precision=6)
    uuid_type = postgresql.UUID(as_uuid=True)
    op.create_table(
        "users",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=True),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("email_verified_at", timestamp, nullable=True),
        sa.Column("created_at", timestamp, nullable=False),
        sa.Column("updated_at", timestamp, nullable=False),
        sa.CheckConstraint("kind IN ('HUMAN', 'SYSTEM')", name="users_kind_check"),
        sa.CheckConstraint("role IN ('USER', 'ADMIN')", name="users_role_check"),
        sa.CheckConstraint(
            "status IN ('PENDING', 'ACTIVE', 'DISABLED')",
            name="users_status_check",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_users_normalized_email",
        "users",
        [sa.text("lower(email)")],
        unique=True,
    )
    op.create_table(
        "user_password_credentials",
        sa.Column("user_id", uuid_type, nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=False),
        sa.Column("password_changed_at", timestamp, nullable=False),
        sa.Column("created_at", timestamp, nullable=False),
        sa.Column("updated_at", timestamp, nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_user_password_credentials_user",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.execute(
        sa.text(
            """
            INSERT INTO users (
                id, email, display_name, kind, role, status,
                email_verified_at, created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), 'legacy-owner@internal.invalid', 'Legacy Owner',
                'SYSTEM', 'ADMIN', 'DISABLED', NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
            """
        ).bindparams(id=LEGACY_OWNER_ID)
    )

    owner_default = sa.text(f"'{LEGACY_OWNER_ID}'::uuid")
    for table in OWNED_TABLES:
        op.add_column(
            table,
            sa.Column("user_id", uuid_type, nullable=False, server_default=owner_default),
        )
        op.create_foreign_key(
            f"fk_{table}_user",
            table,
            "users",
            ["user_id"],
            ["id"],
        )
        op.create_index(f"idx_{table}_user_id", table, ["user_id"])

    op.execute(
        sa.text("UPDATE voice_interview_sessions SET user_id = :id").bindparams(id=LEGACY_OWNER_ID)
    )
    op.alter_column(
        "voice_interview_sessions",
        "user_id",
        existing_type=sa.String(length=255),
        type_=uuid_type,
        nullable=False,
        server_default=owner_default,
        postgresql_using="user_id::uuid",
    )
    op.create_foreign_key(
        "fk_voice_interview_sessions_user",
        "voice_interview_sessions",
        "users",
        ["user_id"],
        ["id"],
    )
    op.create_index(
        "idx_voice_interview_sessions_user_id",
        "voice_interview_sessions",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_voice_interview_sessions_user_id",
        table_name="voice_interview_sessions",
    )
    op.drop_constraint(
        "fk_voice_interview_sessions_user",
        "voice_interview_sessions",
        type_="foreignkey",
    )
    op.alter_column(
        "voice_interview_sessions",
        "user_id",
        existing_type=postgresql.UUID(as_uuid=True),
        type_=sa.String(length=255),
        nullable=True,
        server_default=None,
        postgresql_using="user_id::text",
    )
    for table in reversed(OWNED_TABLES):
        op.drop_index(f"idx_{table}_user_id", table_name=table)
        op.drop_constraint(f"fk_{table}_user", table, type_="foreignkey")
        op.drop_column(table, "user_id")
    op.drop_table("user_password_credentials")
    op.drop_index("uq_users_normalized_email", table_name="users")
    op.drop_table("users")
