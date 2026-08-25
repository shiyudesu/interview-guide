from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID as PythonUUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Identity,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import DOUBLE_PRECISION, JSON, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from interview_guide.common.db.base import Base

TIMESTAMP_6 = TIMESTAMP(timezone=False, precision=6)
LEGACY_OWNER_ID = PythonUUID("00000000-0000-0000-0000-000000000001")


class UserAccount(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("kind IN ('HUMAN', 'SYSTEM')", name="users_kind_check"),
        CheckConstraint("role IN ('USER', 'ADMIN')", name="users_role_check"),
        CheckConstraint(
            "status IN ('PENDING', 'ACTIVE', 'DISABLED')",
            name="users_status_check",
        ),
        Index("uq_users_normalized_email", func.lower(text("email")), unique=True),
    )

    id: Mapped[PythonUUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(100))
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(TIMESTAMP_6)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP_6, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP_6, nullable=False)


class UserPasswordCredential(Base):
    __tablename__ = "user_password_credentials"

    user_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", name="fk_user_password_credentials_user", ondelete="CASCADE"),
        primary_key=True,
    )
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    password_changed_at: Mapped[datetime] = mapped_column(TIMESTAMP_6, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP_6, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP_6, nullable=False)


class InterviewSchedule(Base):
    __tablename__ = "interview_schedule"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'COMPLETED', 'CANCELLED', 'RESCHEDULED')",
            name="interview_schedule_status_check",
        ),
        Index("idx_interview_schedule_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(always=False),
        primary_key=True,
    )
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(TIMESTAMP_6)
    interview_time: Mapped[datetime] = mapped_column(TIMESTAMP_6, nullable=False)
    interview_type: Mapped[str | None] = mapped_column(String(255))
    interviewer: Mapped[str | None] = mapped_column(String(255))
    meeting_link: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    position: Mapped[str] = mapped_column(String(255), nullable=False)
    round_number: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(255), nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(TIMESTAMP_6)
    user_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", name="fk_interview_schedule_user"),
        nullable=False,
        server_default=text("'00000000-0000-0000-0000-000000000001'::uuid"),
    )


class Resume(Base):
    __tablename__ = "resumes"
    __table_args__ = (
        CheckConstraint(
            "analyze_status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED')",
            name="resumes_analyze_status_check",
        ),
        UniqueConstraint("file_hash", name="idx_resume_hash"),
        Index("idx_resumes_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(always=False),
        primary_key=True,
    )
    access_count: Mapped[int | None] = mapped_column(Integer)
    analyze_error: Mapped[str | None] = mapped_column(String(500))
    analyze_status: Mapped[str | None] = mapped_column(String(20))
    content_type: Mapped[str | None] = mapped_column(String(255))
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size: Mapped[int | None] = mapped_column(BigInteger)
    last_accessed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP_6)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    resume_text: Mapped[str | None] = mapped_column(Text)
    storage_key: Mapped[str | None] = mapped_column(String(500))
    storage_url: Mapped[str | None] = mapped_column(String(1000))
    uploaded_at: Mapped[datetime] = mapped_column(TIMESTAMP_6, nullable=False)
    user_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", name="fk_resumes_user"),
        nullable=False,
        server_default=text("'00000000-0000-0000-0000-000000000001'::uuid"),
    )


class ResumeAnalysis(Base):
    __tablename__ = "resume_analyses"

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(always=False),
        primary_key=True,
    )
    analyzed_at: Mapped[datetime] = mapped_column(TIMESTAMP_6, nullable=False)
    content_score: Mapped[int | None] = mapped_column(Integer)
    expression_score: Mapped[int | None] = mapped_column(Integer)
    overall_score: Mapped[int | None] = mapped_column(Integer)
    project_score: Mapped[int | None] = mapped_column(Integer)
    skill_match_score: Mapped[int | None] = mapped_column(Integer)
    strengths_json: Mapped[str | None] = mapped_column(Text)
    structure_score: Mapped[int | None] = mapped_column(Integer)
    suggestions_json: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    resume_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "resumes.id",
            name="fkrp4f11h23bp0j118yan185lr5",
        ),
        nullable=False,
    )


class InterviewSession(Base):
    __tablename__ = "interview_sessions"
    __table_args__ = (
        CheckConstraint(
            "evaluate_status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED')",
            name="interview_sessions_evaluate_status_check",
        ),
        CheckConstraint(
            "status IN ('CREATED', 'IN_PROGRESS', 'COMPLETED', 'EVALUATED')",
            name="interview_sessions_status_check",
        ),
        CheckConstraint(
            "channel IN ('TEXT', 'KNOWLEDGE_BASE', 'VOICE')",
            name="interview_sessions_channel_check",
        ),
        UniqueConstraint("session_id", name="uk42bhenf7mu90ochoc1efpg3xa"),
        Index(
            "idx_interview_session_resume_created",
            "resume_id",
            "created_at",
        ),
        Index(
            "idx_interview_session_resume_status_created",
            "resume_id",
            "status",
            "created_at",
        ),
        Index(
            "idx_interview_session_skill_created",
            "skill_id",
            "created_at",
        ),
        Index(
            "uk_interview_sessions_request_id",
            "request_id",
            unique=True,
        ),
        Index("idx_interview_sessions_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(always=False),
        primary_key=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP_6)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP_6, nullable=False)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    context_json: Mapped[str | None] = mapped_column(Text)
    current_question_id: Mapped[PythonUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "interview_questions.id",
            name="fk_interview_sessions_current_question",
            use_alter=True,
        ),
    )
    difficulty: Mapped[str | None] = mapped_column(String(16))
    evaluate_error: Mapped[str | None] = mapped_column(String(500))
    evaluate_status: Mapped[str | None] = mapped_column(String(20))
    improvements_json: Mapped[str | None] = mapped_column(Text)
    interview_category: Mapped[str | None] = mapped_column(
        String(64),
        comment="知识库面试方向（来自题库 category，普通面试为 NULL）",
    )
    knowledge_base_id: Mapped[int | None] = mapped_column(BigInteger)
    llm_provider: Mapped[str | None] = mapped_column(String(50))
    overall_feedback: Mapped[str | None] = mapped_column(Text)
    overall_score: Mapped[int | None] = mapped_column(Integer)
    max_follow_ups_per_main: Mapped[int] = mapped_column(Integer, nullable=False)
    planned_main_question_count: Mapped[int] = mapped_column(Integer, nullable=False)
    reference_answers_json: Mapped[str | None] = mapped_column(Text)
    request_id: Mapped[str | None] = mapped_column(String(64))
    resume_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey(
            "resumes.id",
            name="fkhresfe6p1s53klvmqhxxissa2",
        ),
    )
    session_id: Mapped[str] = mapped_column(String(36), nullable=False)
    skill_id: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str | None] = mapped_column(String(20))
    strengths_json: Mapped[str | None] = mapped_column(Text)
    user_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", name="fk_interview_sessions_user"),
        nullable=False,
        server_default=text("'00000000-0000-0000-0000-000000000001'::uuid"),
    )


class InterviewQuestionRecord(Base):
    __tablename__ = "interview_questions"
    __table_args__ = (
        UniqueConstraint(
            "interview_session_id",
            "main_order",
            "follow_up_order",
            name="uk_interview_question_order",
        ),
        UniqueConstraint(
            "id",
            "interview_session_id",
            name="uk_interview_question_id_session",
        ),
        ForeignKeyConstraint(
            ("parent_question_id", "interview_session_id"),
            ("interview_questions.id", "interview_questions.interview_session_id"),
            name="fk_interview_question_parent_session",
            deferrable=True,
            initially="DEFERRED",
        ),
        CheckConstraint(
            "(kind = 'MAIN' AND parent_question_id IS NULL AND follow_up_order = 0) "
            "OR (kind = 'FOLLOW_UP' AND parent_question_id IS NOT NULL "
            "AND follow_up_order >= 1)",
            name="interview_questions_kind_check",
        ),
        Index(
            "idx_interview_questions_session_order",
            "interview_session_id",
            "main_order",
            "follow_up_order",
        ),
    )

    id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        server_default=text("public.uuid_generate_v4()"),
        primary_key=True,
    )
    interview_session_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "interview_sessions.id",
            name="fk_interview_questions_session",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    phase: Mapped[str | None] = mapped_column(String(16))
    main_order: Mapped[int] = mapped_column(Integer, nullable=False)
    follow_up_order: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_question_id: Mapped[PythonUUID | None] = mapped_column(UUID(as_uuid=True))
    question: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    category: Mapped[str | None] = mapped_column(String(255))
    topic_summary: Mapped[str | None] = mapped_column(String(500))
    reference_answer: Mapped[str | None] = mapped_column(Text)
    key_points_json: Mapped[str | None] = mapped_column(Text)
    scoring_rubric: Mapped[str | None] = mapped_column(Text)
    source_context: Mapped[str | None] = mapped_column(Text)
    source_question_id: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP_6, nullable=False)


class InterviewTurnRecord(Base):
    __tablename__ = "interview_turns"
    __table_args__ = (
        UniqueConstraint(
            "interview_session_id",
            "request_id",
            name="uk_interview_turn_request",
        ),
        UniqueConstraint(
            "interview_session_id",
            "question_id",
            name="uk_interview_turn_question",
        ),
        CheckConstraint(
            "decision_status IN ('PROCESSING', 'COMPLETED', 'FALLBACK', 'FAILED')",
            name="interview_turns_status_check",
        ),
        CheckConstraint(
            "action IS NULL OR action IN ('FOLLOW_UP', 'NEXT_MAIN', 'COMPLETE')",
            name="interview_turns_action_check",
        ),
        Index(
            "idx_interview_turns_session_answered",
            "interview_session_id",
            "answered_at",
        ),
        Index(
            "idx_interview_turns_processing_lease",
            "decision_status",
            "lease_expires_at",
        ),
    )

    id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        server_default=text("public.uuid_generate_v4()"),
        primary_key=True,
    )
    interview_session_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "interview_sessions.id",
            name="fk_interview_turns_session",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    question_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "interview_questions.id",
            name="fk_interview_turns_question",
        ),
        nullable=False,
    )
    request_id: Mapped[str] = mapped_column(String(64), nullable=False)
    answer: Mapped[str | None] = mapped_column(Text)
    answer_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str | None] = mapped_column(String(16))
    acknowledgement: Mapped[str | None] = mapped_column(String(200))
    next_question_id: Mapped[PythonUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "interview_questions.id",
            name="fk_interview_turns_next_question",
        ),
    )
    decision_reason: Mapped[str | None] = mapped_column(String(500))
    reason_code: Mapped[str | None] = mapped_column(String(64))
    target_topic: Mapped[str | None] = mapped_column(String(128))
    confidence: Mapped[float | None] = mapped_column(DOUBLE_PRECISION)
    decision_status: Mapped[str] = mapped_column(String(16), nullable=False)
    provider_id: Mapped[str | None] = mapped_column(String(64))
    model_name: Mapped[str | None] = mapped_column(String(255))
    prompt_version: Mapped[str | None] = mapped_column(String(32))
    schema_version: Mapped[str | None] = mapped_column(String(32))
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
    total_tokens: Mapped[int | None] = mapped_column(Integer)
    decision_duration_ms: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(String(500))
    processing_started_at: Mapped[datetime] = mapped_column(TIMESTAMP_6, nullable=False)
    lease_expires_at: Mapped[datetime] = mapped_column(TIMESTAMP_6, nullable=False)
    answered_at: Mapped[datetime] = mapped_column(TIMESTAMP_6, nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(TIMESTAMP_6)


class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"
    __table_args__ = (
        CheckConstraint(
            "vector_status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED')",
            name="knowledge_bases_vector_status_check",
        ),
        CheckConstraint(
            "question_gen_status IN ('NONE', 'QUEUED', 'PROCESSING', 'COMPLETED', 'FAILED')",
            name="knowledge_bases_question_gen_status_check",
        ),
        UniqueConstraint("file_hash", name="idx_kb_hash"),
        Index("idx_kb_category", "category"),
        Index(
            "idx_kb_question_gen_status_updated",
            "question_gen_status",
            "question_gen_updated_at",
        ),
        Index("idx_knowledge_bases_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(always=False),
        primary_key=True,
    )
    access_count: Mapped[int | None] = mapped_column(Integer)
    category: Mapped[str | None] = mapped_column(String(100))
    chunk_count: Mapped[int | None] = mapped_column(Integer)
    content_type: Mapped[str | None] = mapped_column(String(255))
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size: Mapped[int | None] = mapped_column(BigInteger)
    last_accessed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP_6)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    question_count: Mapped[int | None] = mapped_column(Integer)
    question_gen_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'NONE'"),
    )
    question_gen_error: Mapped[str | None] = mapped_column(String(500))
    question_gen_task_id: Mapped[str | None] = mapped_column(String(36))
    question_gen_config: Mapped[str | None] = mapped_column(Text)
    question_gen_message: Mapped[str | None] = mapped_column(String(500))
    question_gen_saved_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    question_gen_skipped_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    question_gen_updated_at: Mapped[datetime | None] = mapped_column(TIMESTAMP_6)
    storage_key: Mapped[str | None] = mapped_column(String(500))
    storage_url: Mapped[str | None] = mapped_column(String(1000))
    uploaded_at: Mapped[datetime] = mapped_column(TIMESTAMP_6, nullable=False)
    vector_error: Mapped[str | None] = mapped_column(String(500))
    vector_status: Mapped[str | None] = mapped_column(String(20))
    user_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", name="fk_knowledge_bases_user"),
        nullable=False,
        server_default=text("'00000000-0000-0000-0000-000000000001'::uuid"),
    )


class KnowledgeBaseQuestion(Base):
    __tablename__ = "knowledge_base_questions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT', 'ACTIVE', 'ARCHIVED', 'STALE')",
            name="knowledge_base_questions_status_check",
        ),
        Index(
            "idx_kb_question_kb_status",
            "knowledge_base_id",
            "status",
        ),
        Index(
            "idx_kb_question_skill_difficulty",
            "skill_id",
            "difficulty",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(always=False),
        primary_key=True,
    )
    category: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP_6, nullable=False)
    difficulty: Mapped[str | None] = mapped_column(String(16))
    follow_ups_json: Mapped[str | None] = mapped_column(Text)
    kb_content_hash: Mapped[str | None] = mapped_column(String(64))
    key_points_json: Mapped[str | None] = mapped_column(Text)
    knowledge_base_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey(
            "knowledge_bases.id",
            name="fkosobqu06r3tbr13ca043slftw",
        ),
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    reference_answer: Mapped[str | None] = mapped_column(Text)
    scoring_rubric: Mapped[str | None] = mapped_column(Text)
    skill_id: Mapped[str] = mapped_column(String(64), nullable=False)
    source_context: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    topic_summary: Mapped[str | None] = mapped_column(String(300))
    type: Mapped[str | None] = mapped_column(String(64))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP_6, nullable=False)


class LlmGlobalSetting(Base):
    __tablename__ = "llm_global_setting"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP_6, nullable=False)
    default_chat_provider_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    default_embedding_provider_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP_6, nullable=False)


class LlmProviderConfig(Base):
    __tablename__ = "llm_provider_config"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    api_key_ciphertext: Mapped[str] = mapped_column(String(4096), nullable=False)
    api_key_nonce: Mapped[str] = mapped_column(String(64), nullable=False)
    base_url: Mapped[str] = mapped_column(String(512), nullable=False)
    builtin: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP_6, nullable=False)
    embedding_dimensions: Mapped[int | None] = mapped_column(Integer)
    embedding_model: Mapped[str | None] = mapped_column(String(128))
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    supports_embedding: Mapped[bool] = mapped_column(Boolean, nullable=False)
    temperature: Mapped[float | None] = mapped_column(DOUBLE_PRECISION)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP_6, nullable=False)


class VoiceModelConfig(Base):
    __tablename__ = "voice_model_config"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    asr_provider_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey(
            "llm_provider_config.id",
            name="fk_voice_model_config_asr_provider",
        ),
        nullable=False,
    )
    asr_url: Mapped[str] = mapped_column(String(512), nullable=False)
    asr_model: Mapped[str] = mapped_column(String(128), nullable=False)
    asr_language: Mapped[str] = mapped_column(String(32), nullable=False)
    asr_format: Mapped[str] = mapped_column(String(32), nullable=False)
    asr_sample_rate: Mapped[int] = mapped_column(Integer, nullable=False)
    asr_enable_turn_detection: Mapped[bool] = mapped_column(Boolean, nullable=False)
    asr_turn_detection_type: Mapped[str] = mapped_column(String(64), nullable=False)
    asr_turn_detection_threshold: Mapped[float] = mapped_column(
        DOUBLE_PRECISION,
        nullable=False,
    )
    asr_silence_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    tts_provider_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey(
            "llm_provider_config.id",
            name="fk_voice_model_config_tts_provider",
        ),
        nullable=False,
    )
    tts_url: Mapped[str] = mapped_column(String(512), nullable=False)
    tts_model: Mapped[str] = mapped_column(String(128), nullable=False)
    tts_voice: Mapped[str] = mapped_column(String(128), nullable=False)
    tts_format: Mapped[str] = mapped_column(String(32), nullable=False)
    tts_sample_rate: Mapped[int] = mapped_column(Integer, nullable=False)
    tts_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    tts_language_type: Mapped[str] = mapped_column(String(32), nullable=False)
    tts_speech_rate: Mapped[float] = mapped_column(DOUBLE_PRECISION, nullable=False)
    tts_volume: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP_6, nullable=False)


class RagChatSession(Base):
    __tablename__ = "rag_chat_sessions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ACTIVE', 'ARCHIVED')",
            name="rag_chat_sessions_status_check",
        ),
        Index("idx_rag_session_updated", "updated_at"),
        Index("idx_rag_chat_sessions_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(always=False),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP_6, nullable=False)
    is_pinned: Mapped[bool | None] = mapped_column(
        Boolean,
        server_default=text("false"),
    )
    message_count: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str | None] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(TIMESTAMP_6)
    user_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", name="fk_rag_chat_sessions_user"),
        nullable=False,
        server_default=text("'00000000-0000-0000-0000-000000000001'::uuid"),
    )


class RagChatMessage(Base):
    __tablename__ = "rag_chat_messages"
    __table_args__ = (
        CheckConstraint(
            "type IN ('USER', 'ASSISTANT')",
            name="rag_chat_messages_type_check",
        ),
        Index("idx_rag_message_order", "session_id", "message_order"),
        Index("idx_rag_message_session", "session_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(always=False),
        primary_key=True,
    )
    completed: Mapped[bool | None] = mapped_column(Boolean)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP_6, nullable=False)
    message_order: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(TIMESTAMP_6)
    session_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "rag_chat_sessions.id",
            name="fkfohypaygc0qfqo62vyaxlbntn",
        ),
        nullable=False,
    )


class RagSessionKnowledgeBase(Base):
    __tablename__ = "rag_session_knowledge_bases"
    __table_args__ = (
        PrimaryKeyConstraint(
            "session_id",
            "knowledge_base_id",
        ),
    )

    session_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "rag_chat_sessions.id",
            name="fkqfob368wcvb82elsjkx2troqu",
        ),
        nullable=False,
    )
    knowledge_base_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "knowledge_bases.id",
            name="fkjsfwqyt1ntgr0fcvjieq8c0nb",
        ),
        nullable=False,
    )


class VectorStore(Base):
    __tablename__ = "vector_store"
    __table_args__ = (
        Index(
            "vector_store_embedding_hnsw_idx",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("public.uuid_generate_v4()"),
    )
    content: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024))


class VoiceInterviewMessage(Base):
    __tablename__ = "voice_interview_messages"
    __table_args__ = (
        CheckConstraint(
            "phase IN ('INTRO', 'TECH', 'PROJECT', 'HR', 'COMPLETED')",
            name="voice_interview_messages_phase_check",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(always=False),
        primary_key=True,
    )
    interview_turn_id: Mapped[PythonUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "interview_turns.id",
            name="fk_voice_interview_messages_turn",
            ondelete="SET NULL",
        ),
        unique=True,
    )
    ai_generated_text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime | None] = mapped_column(TIMESTAMP_6)
    message_type: Mapped[str] = mapped_column(String(255), nullable=False)
    phase: Mapped[str | None] = mapped_column(String(255))
    sequence_num: Mapped[int | None] = mapped_column(Integer)
    session_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey(
            "voice_interview_sessions.id",
            name="fk_voice_interview_messages_session",
            ondelete="CASCADE",
        ),
    )
    timestamp: Mapped[datetime | None] = mapped_column(TIMESTAMP_6)
    user_recognized_text: Mapped[str | None] = mapped_column(Text)


class VoiceInterviewSession(Base):
    __tablename__ = "voice_interview_sessions"
    __table_args__ = (
        CheckConstraint(
            "current_phase IN ('INTRO', 'TECH', 'PROJECT', 'HR', 'COMPLETED')",
            name="voice_interview_sessions_current_phase_check",
        ),
        CheckConstraint(
            "evaluate_status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED')",
            name="voice_interview_sessions_evaluate_status_check",
        ),
        CheckConstraint(
            "status IN ('IN_PROGRESS', 'PAUSED', 'COMPLETED', 'FAILED')",
            name="voice_interview_sessions_status_check",
        ),
        Index("idx_voice_interview_sessions_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(always=False),
        primary_key=True,
    )
    interview_session_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "interview_sessions.id",
            name="fk_voice_interview_sessions_interview",
            ondelete="CASCADE",
        ),
        nullable=False,
        unique=True,
    )
    actual_duration: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime | None] = mapped_column(TIMESTAMP_6)
    current_phase: Mapped[str | None] = mapped_column(String(255))
    custom_jd_text: Mapped[str | None] = mapped_column(Text)
    difficulty: Mapped[str | None] = mapped_column(String(16))
    end_time: Mapped[datetime | None] = mapped_column(TIMESTAMP_6)
    evaluate_error: Mapped[str | None] = mapped_column(String(500))
    evaluate_status: Mapped[str | None] = mapped_column(String(255))
    hr_enabled: Mapped[bool | None] = mapped_column(Boolean)
    intro_enabled: Mapped[bool | None] = mapped_column(Boolean)
    llm_provider: Mapped[str | None] = mapped_column(String(50))
    paused_at: Mapped[datetime | None] = mapped_column(TIMESTAMP_6)
    planned_duration: Mapped[int | None] = mapped_column(Integer)
    project_enabled: Mapped[bool | None] = mapped_column(Boolean)
    resume_id: Mapped[int | None] = mapped_column(BigInteger)
    resumed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP_6)
    role_type: Mapped[str] = mapped_column(String(255), nullable=False)
    skill_id: Mapped[str | None] = mapped_column(String(64))
    start_time: Mapped[datetime | None] = mapped_column(TIMESTAMP_6)
    status: Mapped[str | None] = mapped_column(String(255))
    tech_enabled: Mapped[bool | None] = mapped_column(Boolean)
    updated_at: Mapped[datetime | None] = mapped_column(TIMESTAMP_6)
    user_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", name="fk_voice_interview_sessions_user"),
        nullable=False,
        server_default=text("'00000000-0000-0000-0000-000000000001'::uuid"),
    )
