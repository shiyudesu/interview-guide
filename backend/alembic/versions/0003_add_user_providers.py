"""Add user-scoped Provider and model settings.

Revision ID: 0003_add_user_providers
Revises: 0002_add_auth_and_ownership
Create Date: 2026-08-25
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003_add_user_providers"
down_revision: str | Sequence[str] | None = "0002_add_auth_and_ownership"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEGACY_OWNER_ID = "00000000-0000-0000-0000-000000000001"
PROVIDER_NAMESPACE = "2df6f54d-4978-4f6f-908f-c4ea59da42d8"


def upgrade() -> None:
    uuid_type = postgresql.UUID(as_uuid=True)
    timestamp = postgresql.TIMESTAMP(timezone=False, precision=6)
    op.create_table(
        "user_llm_providers",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("user_id", uuid_type, nullable=False),
        sa.Column("alias", sa.String(length=64), nullable=False),
        sa.Column("api_key_ciphertext", sa.String(length=4096), nullable=True),
        sa.Column("api_key_nonce", sa.String(length=64), nullable=True),
        sa.Column("encryption_version", sa.Integer(), nullable=False),
        sa.Column("base_url", sa.String(length=512), nullable=False),
        sa.Column("builtin", sa.Boolean(), nullable=False),
        sa.Column("created_at", timestamp, nullable=False),
        sa.Column("embedding_dimensions", sa.Integer(), nullable=True),
        sa.Column("embedding_model", sa.String(length=128), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("supports_embedding", sa.Boolean(), nullable=False),
        sa.Column("temperature", sa.DOUBLE_PRECISION(), nullable=True),
        sa.Column("updated_at", timestamp, nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_user_llm_providers_user",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "alias", name="uq_user_llm_providers_alias"),
    )
    op.create_index(
        "idx_user_llm_providers_user_id",
        "user_llm_providers",
        ["user_id"],
    )
    op.create_table(
        "user_ai_settings",
        sa.Column("user_id", uuid_type, nullable=False),
        sa.Column("default_chat_provider_id", uuid_type, nullable=False),
        sa.Column("default_embedding_provider_id", uuid_type, nullable=False),
        sa.Column("created_at", timestamp, nullable=False),
        sa.Column("updated_at", timestamp, nullable=False),
        sa.ForeignKeyConstraint(
            ["default_chat_provider_id"],
            ["user_llm_providers.id"],
            name="fk_user_ai_settings_chat_provider",
        ),
        sa.ForeignKeyConstraint(
            ["default_embedding_provider_id"],
            ["user_llm_providers.id"],
            name="fk_user_ai_settings_embedding_provider",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_user_ai_settings_user",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_table(
        "user_voice_settings",
        sa.Column("user_id", uuid_type, nullable=False),
        sa.Column("asr_provider_id", uuid_type, nullable=False),
        sa.Column("asr_url", sa.String(length=512), nullable=False),
        sa.Column("asr_model", sa.String(length=128), nullable=False),
        sa.Column("asr_language", sa.String(length=32), nullable=False),
        sa.Column("asr_format", sa.String(length=32), nullable=False),
        sa.Column("asr_sample_rate", sa.Integer(), nullable=False),
        sa.Column("asr_enable_turn_detection", sa.Boolean(), nullable=False),
        sa.Column("asr_turn_detection_type", sa.String(length=64), nullable=False),
        sa.Column("asr_turn_detection_threshold", sa.DOUBLE_PRECISION(), nullable=False),
        sa.Column("asr_silence_ms", sa.Integer(), nullable=False),
        sa.Column("tts_provider_id", uuid_type, nullable=False),
        sa.Column("tts_url", sa.String(length=512), nullable=False),
        sa.Column("tts_model", sa.String(length=128), nullable=False),
        sa.Column("tts_voice", sa.String(length=128), nullable=False),
        sa.Column("tts_format", sa.String(length=32), nullable=False),
        sa.Column("tts_sample_rate", sa.Integer(), nullable=False),
        sa.Column("tts_mode", sa.String(length=32), nullable=False),
        sa.Column("tts_language_type", sa.String(length=32), nullable=False),
        sa.Column("tts_speech_rate", sa.DOUBLE_PRECISION(), nullable=False),
        sa.Column("tts_volume", sa.Integer(), nullable=False),
        sa.Column("updated_at", timestamp, nullable=False),
        sa.ForeignKeyConstraint(
            ["asr_provider_id"],
            ["user_llm_providers.id"],
            name="fk_user_voice_settings_asr_provider",
        ),
        sa.ForeignKeyConstraint(
            ["tts_provider_id"],
            ["user_llm_providers.id"],
            name="fk_user_voice_settings_tts_provider",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_user_voice_settings_user",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id"),
    )
    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            INSERT INTO user_llm_providers (
                id, user_id, alias, api_key_ciphertext, api_key_nonce,
                encryption_version, base_url, builtin, created_at,
                embedding_dimensions, embedding_model, enabled, model,
                supports_embedding, temperature, updated_at
            )
            SELECT
                public.uuid_generate_v5(CAST(:namespace AS uuid), provider.id),
                CAST(:user_id AS uuid), provider.id,
                provider.api_key_ciphertext, provider.api_key_nonce, 0,
                provider.base_url, provider.builtin, provider.created_at,
                provider.embedding_dimensions, provider.embedding_model,
                provider.enabled, provider.model, provider.supports_embedding,
                provider.temperature, provider.updated_at
            FROM llm_provider_config AS provider
            """
        ),
        {"namespace": PROVIDER_NAMESPACE, "user_id": LEGACY_OWNER_ID},
    )
    connection.execute(
        sa.text(
            """
            INSERT INTO user_llm_providers (
                id, user_id, alias, api_key_ciphertext, api_key_nonce,
                encryption_version, base_url, builtin, created_at,
                embedding_dimensions, embedding_model, enabled, model,
                supports_embedding, temperature, updated_at
            )
            SELECT
                public.uuid_generate_v5(CAST(:namespace AS uuid), 'dashscope'),
                CAST(:user_id AS uuid), 'dashscope', NULL, NULL, 1,
                'https://dashscope.aliyuncs.com/compatible-mode/v1', TRUE,
                CURRENT_TIMESTAMP, 1024, 'qwen3.7-text-embedding', TRUE,
                'qwen3.7-max', TRUE, NULL, CURRENT_TIMESTAMP
            WHERE NOT EXISTS (
                SELECT 1 FROM user_llm_providers
                WHERE user_id = CAST(:user_id AS uuid)
            )
            """
        ),
        {"namespace": PROVIDER_NAMESPACE, "user_id": LEGACY_OWNER_ID},
    )
    connection.execute(
        sa.text(
            """
            INSERT INTO user_ai_settings (
                user_id, default_chat_provider_id, default_embedding_provider_id,
                created_at, updated_at
            )
            SELECT CAST(:user_id AS uuid), chat.id, embedding.id,
                   setting.created_at, setting.updated_at
            FROM llm_global_setting AS setting
            JOIN user_llm_providers AS chat
              ON chat.user_id = CAST(:user_id AS uuid)
             AND chat.alias = setting.default_chat_provider_id
            JOIN user_llm_providers AS embedding
              ON embedding.user_id = CAST(:user_id AS uuid)
             AND embedding.alias = setting.default_embedding_provider_id
            WHERE setting.id = 1
            """
        ),
        {"user_id": LEGACY_OWNER_ID},
    )
    connection.execute(
        sa.text(
            """
            INSERT INTO user_ai_settings (
                user_id, default_chat_provider_id, default_embedding_provider_id,
                created_at, updated_at
            )
            SELECT CAST(:user_id AS uuid), provider.id, provider.id,
                   CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            FROM user_llm_providers AS provider
            WHERE provider.user_id = CAST(:user_id AS uuid)
              AND NOT EXISTS (
                  SELECT 1 FROM user_ai_settings
                  WHERE user_id = CAST(:user_id AS uuid)
              )
            ORDER BY CASE WHEN provider.alias = 'dashscope' THEN 0 ELSE 1 END, provider.alias
            LIMIT 1
            """
        ),
        {"user_id": LEGACY_OWNER_ID},
    )
    connection.execute(
        sa.text(
            """
            INSERT INTO user_voice_settings (
                user_id, asr_provider_id, asr_url, asr_model, asr_language,
                asr_format, asr_sample_rate, asr_enable_turn_detection,
                asr_turn_detection_type, asr_turn_detection_threshold,
                asr_silence_ms, tts_provider_id, tts_url, tts_model,
                tts_voice, tts_format, tts_sample_rate, tts_mode,
                tts_language_type, tts_speech_rate, tts_volume, updated_at
            )
            SELECT
                CAST(:user_id AS uuid), asr.id, voice.asr_url, voice.asr_model,
                voice.asr_language, voice.asr_format, voice.asr_sample_rate,
                voice.asr_enable_turn_detection, voice.asr_turn_detection_type,
                voice.asr_turn_detection_threshold, voice.asr_silence_ms,
                tts.id, voice.tts_url, voice.tts_model, voice.tts_voice,
                voice.tts_format, voice.tts_sample_rate, voice.tts_mode,
                voice.tts_language_type, voice.tts_speech_rate,
                voice.tts_volume, voice.updated_at
            FROM voice_model_config AS voice
            JOIN user_llm_providers AS asr
              ON asr.user_id = CAST(:user_id AS uuid)
             AND asr.alias = voice.asr_provider_id
            JOIN user_llm_providers AS tts
              ON tts.user_id = CAST(:user_id AS uuid)
             AND tts.alias = voice.tts_provider_id
            WHERE voice.id = 1
            """
        ),
        {"user_id": LEGACY_OWNER_ID},
    )
    connection.execute(
        sa.text(
            """
            INSERT INTO user_voice_settings (
                user_id, asr_provider_id, asr_url, asr_model, asr_language,
                asr_format, asr_sample_rate, asr_enable_turn_detection,
                asr_turn_detection_type, asr_turn_detection_threshold,
                asr_silence_ms, tts_provider_id, tts_url, tts_model,
                tts_voice, tts_format, tts_sample_rate, tts_mode,
                tts_language_type, tts_speech_rate, tts_volume, updated_at
            )
            SELECT
                CAST(:user_id AS uuid), provider.id,
                'wss://dashscope.aliyuncs.com/api-ws/v1/realtime',
                'qwen3-asr-flash-realtime', 'zh', 'pcm', 16000, TRUE,
                'server_vad', 0, 2000, provider.id,
                'wss://dashscope.aliyuncs.com/api-ws/v1/realtime',
                'qwen3-tts-flash-realtime', 'Cherry', 'pcm', 24000,
                'commit', 'Chinese', 1, 60, CURRENT_TIMESTAMP
            FROM user_llm_providers AS provider
            WHERE provider.user_id = CAST(:user_id AS uuid)
              AND NOT EXISTS (
                  SELECT 1 FROM user_voice_settings
                  WHERE user_id = CAST(:user_id AS uuid)
              )
            ORDER BY CASE WHEN provider.alias = 'dashscope' THEN 0 ELSE 1 END, provider.alias
            LIMIT 1
            """
        ),
        {"user_id": LEGACY_OWNER_ID},
    )


def downgrade() -> None:
    op.drop_table("user_voice_settings")
    op.drop_table("user_ai_settings")
    op.drop_index("idx_user_llm_providers_user_id", table_name="user_llm_providers")
    op.drop_table("user_llm_providers")
