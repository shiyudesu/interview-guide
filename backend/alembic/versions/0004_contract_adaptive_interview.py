"""Reset interview data and remove the legacy question-array schema.

Revision ID: 0004_contract_adaptive_interview
Revises: 0003_expand_adaptive_interview
Create Date: 2026-08-19
"""

from __future__ import annotations

import logging
import os

from alembic import op

revision: str = "0004_contract_adaptive_interview"
down_revision: str | None = "0003_expand_adaptive_interview"
branch_labels: str | None = None
depends_on: str | None = None

logger = logging.getLogger("alembic.runtime.migration")
RESET_ENV = "ALLOW_DESTRUCTIVE_INTERVIEW_RESET"
RESET_TABLES = (
    "voice_interview_messages",
    "voice_interview_evaluations",
    "voice_interview_sessions",
    "interview_turns",
    "interview_questions",
    "interview_answers",
    "interview_sessions",
)


def upgrade() -> None:
    if os.environ.get(RESET_ENV) != "1":
        raise RuntimeError(
            f"Destructive adaptive interview migration requires {RESET_ENV}=1"
        )

    connection = op.get_bind()
    for table in RESET_TABLES:
        count = int(connection.exec_driver_sql(f'SELECT count(*) FROM "{table}"').scalar_one())
        logger.warning("adaptive interview reset table=%s rows=%s", table, count)

    op.execute(
        """
        UPDATE interview_sessions SET current_question_id = NULL;
        DELETE FROM voice_interview_messages;
        DELETE FROM voice_interview_evaluations;
        DELETE FROM voice_interview_sessions;
        DELETE FROM interview_turns;
        DELETE FROM interview_questions;
        DELETE FROM interview_answers;
        DELETE FROM interview_sessions;

        DROP TABLE voice_interview_evaluations;
        DROP TABLE interview_answers;

        ALTER TABLE interview_sessions
          DROP COLUMN current_question_index,
          DROP COLUMN questions_json,
          DROP COLUMN source_type,
          DROP COLUMN total_questions;

        ALTER TABLE interview_sessions
          ALTER COLUMN channel SET NOT NULL,
          ALTER COLUMN planned_main_question_count SET NOT NULL,
          ALTER COLUMN max_follow_ups_per_main SET NOT NULL;

        ALTER TABLE voice_interview_sessions
          ALTER COLUMN interview_session_id SET NOT NULL;
        """
    )


def downgrade() -> None:
    raise RuntimeError("The destructive adaptive interview migration cannot be downgraded")
