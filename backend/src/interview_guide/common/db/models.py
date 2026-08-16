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
    Identity,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import DOUBLE_PRECISION, JSON, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from interview_guide.common.db.base import Base

TIMESTAMP_6 = TIMESTAMP(timezone=False, precision=6)


class InterviewSchedule(Base):
    __tablename__ = "interview_schedule"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'COMPLETED', 'CANCELLED', 'RESCHEDULED')",
            name="interview_schedule_status_check",
        ),
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


class Resume(Base):
    __tablename__ = "resumes"
    __table_args__ = (
        CheckConstraint(
            "analyze_status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED')",
            name="resumes_analyze_status_check",
        ),
        UniqueConstraint("file_hash", name="idx_resume_hash"),
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
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(always=False),
        primary_key=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP_6)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP_6, nullable=False)
    current_question_index: Mapped[int | None] = mapped_column(Integer)
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
    questions_json: Mapped[str | None] = mapped_column(Text)
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
    source_type: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str | None] = mapped_column(String(20))
    strengths_json: Mapped[str | None] = mapped_column(Text)
    total_questions: Mapped[int | None] = mapped_column(Integer)


class InterviewAnswer(Base):
    __tablename__ = "interview_answers"
    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "question_index",
            name="uk_interview_answer_session_question",
        ),
        Index(
            "idx_interview_answer_session_question",
            "session_id",
            "question_index",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(always=False),
        primary_key=True,
    )
    answered_at: Mapped[datetime] = mapped_column(TIMESTAMP_6, nullable=False)
    category: Mapped[str | None] = mapped_column(String(255))
    feedback: Mapped[str | None] = mapped_column(Text)
    key_points_json: Mapped[str | None] = mapped_column(Text)
    question: Mapped[str | None] = mapped_column(Text)
    question_index: Mapped[int | None] = mapped_column(Integer)
    reference_answer: Mapped[str | None] = mapped_column(Text)
    score: Mapped[int | None] = mapped_column(Integer)
    user_answer: Mapped[str | None] = mapped_column(Text)
    session_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "interview_sessions.id",
            name="fkjeqvvamvdarrcbswn6kkiuym9",
        ),
        nullable=False,
    )


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


class RagChatSession(Base):
    __tablename__ = "rag_chat_sessions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ACTIVE', 'ARCHIVED')",
            name="rag_chat_sessions_status_check",
        ),
        Index("idx_rag_session_updated", "updated_at"),
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
            "spring_ai_vector_index",
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


class VoiceInterviewEvaluation(Base):
    __tablename__ = "voice_interview_evaluations"
    __table_args__ = (UniqueConstraint("session_id", name="ukijx8aelak8vqf9n4to88qqrna"),)

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(always=False),
        primary_key=True,
    )
    created_at: Mapped[datetime | None] = mapped_column(TIMESTAMP_6)
    improvements_json: Mapped[str | None] = mapped_column(Text)
    interview_date: Mapped[datetime | None] = mapped_column(TIMESTAMP_6)
    interviewer_role: Mapped[str | None] = mapped_column(String(255))
    overall_feedback: Mapped[str | None] = mapped_column(Text)
    overall_score: Mapped[int | None] = mapped_column(Integer)
    question_evaluations_json: Mapped[str | None] = mapped_column(Text)
    reference_answers_json: Mapped[str | None] = mapped_column(Text)
    session_id: Mapped[int | None] = mapped_column(BigInteger)
    strengths_json: Mapped[str | None] = mapped_column(Text)


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
    ai_generated_text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime | None] = mapped_column(TIMESTAMP_6)
    message_type: Mapped[str] = mapped_column(String(255), nullable=False)
    phase: Mapped[str | None] = mapped_column(String(255))
    sequence_num: Mapped[int | None] = mapped_column(Integer)
    session_id: Mapped[int | None] = mapped_column(BigInteger)
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
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(always=False),
        primary_key=True,
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
    user_id: Mapped[str | None] = mapped_column(String(255))
