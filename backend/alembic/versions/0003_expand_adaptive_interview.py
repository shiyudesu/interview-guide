"""Expand the schema for normalized adaptive interview turns.

Revision ID: 0003_expand_adaptive_interview
Revises: 0002_rename_vector_index
Create Date: 2026-08-19
"""

from __future__ import annotations

from alembic import op

revision: str = "0003_expand_adaptive_interview"
down_revision: str | None = "0002_rename_vector_index"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE interview_sessions
          ADD COLUMN channel VARCHAR(32),
          ADD COLUMN context_json TEXT,
          ADD COLUMN current_question_id UUID,
          ADD COLUMN planned_main_question_count INTEGER,
          ADD COLUMN max_follow_ups_per_main INTEGER;

        ALTER TABLE interview_sessions
          ADD CONSTRAINT interview_sessions_channel_check
          CHECK (channel IN ('TEXT', 'KNOWLEDGE_BASE', 'VOICE'));

        CREATE TABLE interview_questions (
          id UUID PRIMARY KEY DEFAULT public.uuid_generate_v4(),
          interview_session_id BIGINT NOT NULL,
          kind VARCHAR(16) NOT NULL,
          phase VARCHAR(16),
          main_order INTEGER NOT NULL,
          follow_up_order INTEGER NOT NULL,
          parent_question_id UUID,
          question TEXT NOT NULL,
          type VARCHAR(64) NOT NULL,
          category VARCHAR(255),
          topic_summary VARCHAR(500),
          reference_answer TEXT,
          key_points_json TEXT,
          scoring_rubric TEXT,
          source_context TEXT,
          source_question_id BIGINT,
          created_at TIMESTAMP(6) NOT NULL,
          CONSTRAINT fk_interview_questions_session
            FOREIGN KEY (interview_session_id)
            REFERENCES interview_sessions(id) ON DELETE CASCADE,
          CONSTRAINT uk_interview_question_order
            UNIQUE (interview_session_id, main_order, follow_up_order),
          CONSTRAINT uk_interview_question_id_session
            UNIQUE (id, interview_session_id),
          CONSTRAINT fk_interview_question_parent_session
            FOREIGN KEY (parent_question_id, interview_session_id)
            REFERENCES interview_questions(id, interview_session_id)
            DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT interview_questions_kind_check CHECK (
            (kind = 'MAIN' AND parent_question_id IS NULL AND follow_up_order = 0)
            OR
            (kind = 'FOLLOW_UP' AND parent_question_id IS NOT NULL AND follow_up_order >= 1)
          )
        );

        CREATE INDEX idx_interview_questions_session_order
          ON interview_questions(interview_session_id, main_order, follow_up_order);

        ALTER TABLE interview_sessions
          ADD CONSTRAINT fk_interview_sessions_current_question
          FOREIGN KEY (current_question_id) REFERENCES interview_questions(id);

        CREATE TABLE interview_turns (
          id UUID PRIMARY KEY DEFAULT public.uuid_generate_v4(),
          interview_session_id BIGINT NOT NULL,
          question_id UUID NOT NULL,
          request_id VARCHAR(64) NOT NULL,
          answer TEXT,
          answer_hash VARCHAR(64) NOT NULL,
          action VARCHAR(16),
          acknowledgement VARCHAR(200),
          next_question_id UUID,
          decision_reason VARCHAR(500),
          reason_code VARCHAR(64),
          target_topic VARCHAR(128),
          confidence DOUBLE PRECISION,
          decision_status VARCHAR(16) NOT NULL,
          provider_id VARCHAR(64),
          model_name VARCHAR(255),
          prompt_version VARCHAR(32),
          schema_version VARCHAR(32),
          prompt_tokens INTEGER,
          completion_tokens INTEGER,
          total_tokens INTEGER,
          decision_duration_ms INTEGER,
          error VARCHAR(500),
          processing_started_at TIMESTAMP(6) NOT NULL,
          lease_expires_at TIMESTAMP(6) NOT NULL,
          answered_at TIMESTAMP(6) NOT NULL,
          decided_at TIMESTAMP(6),
          CONSTRAINT fk_interview_turns_session
            FOREIGN KEY (interview_session_id)
            REFERENCES interview_sessions(id) ON DELETE CASCADE,
          CONSTRAINT fk_interview_turns_question
            FOREIGN KEY (question_id) REFERENCES interview_questions(id),
          CONSTRAINT fk_interview_turns_next_question
            FOREIGN KEY (next_question_id) REFERENCES interview_questions(id),
          CONSTRAINT uk_interview_turn_request
            UNIQUE (interview_session_id, request_id),
          CONSTRAINT uk_interview_turn_question
            UNIQUE (interview_session_id, question_id),
          CONSTRAINT interview_turns_status_check CHECK (
            decision_status IN ('PROCESSING', 'COMPLETED', 'FALLBACK', 'FAILED')
          ),
          CONSTRAINT interview_turns_action_check CHECK (
            action IS NULL OR action IN ('FOLLOW_UP', 'NEXT_MAIN', 'COMPLETE')
          )
        );

        CREATE INDEX idx_interview_turns_session_answered
          ON interview_turns(interview_session_id, answered_at);
        CREATE INDEX idx_interview_turns_processing_lease
          ON interview_turns(decision_status, lease_expires_at);

        ALTER TABLE voice_interview_sessions
          ADD COLUMN interview_session_id BIGINT;
        ALTER TABLE voice_interview_sessions
          ADD CONSTRAINT fk_voice_interview_sessions_interview
          FOREIGN KEY (interview_session_id)
          REFERENCES interview_sessions(id) ON DELETE CASCADE;
        CREATE UNIQUE INDEX uk_voice_interview_sessions_interview
          ON voice_interview_sessions(interview_session_id);

        ALTER TABLE voice_interview_messages
          ADD COLUMN interview_turn_id UUID;
        ALTER TABLE voice_interview_messages
          ADD CONSTRAINT fk_voice_interview_messages_session
          FOREIGN KEY (session_id)
          REFERENCES voice_interview_sessions(id) ON DELETE CASCADE;
        ALTER TABLE voice_interview_messages
          ADD CONSTRAINT fk_voice_interview_messages_turn
          FOREIGN KEY (interview_turn_id)
          REFERENCES interview_turns(id) ON DELETE SET NULL;
        CREATE UNIQUE INDEX uk_voice_interview_messages_turn
          ON voice_interview_messages(interview_turn_id);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP INDEX IF EXISTS uk_voice_interview_messages_turn;
        ALTER TABLE voice_interview_messages
          DROP CONSTRAINT IF EXISTS fk_voice_interview_messages_turn,
          DROP CONSTRAINT IF EXISTS fk_voice_interview_messages_session,
          DROP COLUMN IF EXISTS interview_turn_id;

        DROP INDEX IF EXISTS uk_voice_interview_sessions_interview;
        ALTER TABLE voice_interview_sessions
          DROP CONSTRAINT IF EXISTS fk_voice_interview_sessions_interview,
          DROP COLUMN IF EXISTS interview_session_id;

        DROP TABLE IF EXISTS interview_turns;
        ALTER TABLE interview_sessions
          DROP CONSTRAINT IF EXISTS fk_interview_sessions_current_question;
        DROP TABLE IF EXISTS interview_questions;
        ALTER TABLE interview_sessions
          DROP CONSTRAINT IF EXISTS interview_sessions_channel_check,
          DROP COLUMN IF EXISTS max_follow_ups_per_main,
          DROP COLUMN IF EXISTS planned_main_question_count,
          DROP COLUMN IF EXISTS current_question_id,
          DROP COLUMN IF EXISTS context_json,
          DROP COLUMN IF EXISTS channel;
        """
    )
