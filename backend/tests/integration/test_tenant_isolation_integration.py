from __future__ import annotations

import os
from collections.abc import AsyncIterator
from datetime import datetime
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select, update

from interview_guide.common.config.settings import Settings
from interview_guide.common.db.models import (
    InterviewQuestionRecord,
    InterviewSchedule,
    InterviewSession,
    InterviewTurnRecord,
    KnowledgeBase,
    KnowledgeBaseQuestion,
    RagChatMessage,
    RagChatSession,
    RagSessionKnowledgeBase,
    Resume,
    ResumeAnalysis,
    UserAccount,
    VoiceInterviewMessage,
    VoiceInterviewSession,
)
from interview_guide.common.db.session import Database
from interview_guide.common.errors import BusinessException
from interview_guide.modules.auth.repository import AuthRepository
from interview_guide.modules.auth.service import utc_now
from interview_guide.modules.interview.models import InterviewChannel, PlannedInterviewQuestion
from interview_guide.modules.interview.repository import InterviewRepository
from interview_guide.modules.interview_schedule.repository import InterviewScheduleRepository
from interview_guide.modules.knowledge_base.rag_chat_repository import RagChatRepository
from interview_guide.modules.knowledge_base.repository import KnowledgeBaseRepository
from interview_guide.modules.resume.repository import ResumeRepository

POSTGRES_URL = os.getenv("TEST_POSTGRES_URL")
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(POSTGRES_URL is None, reason="TEST_POSTGRES_URL is required"),
]


@pytest.fixture
async def tenant_database() -> AsyncIterator[Database]:
    assert POSTGRES_URL is not None
    postgres = urlsplit(POSTGRES_URL)
    database = Database(
        Settings(
            _env_file=None,
            POSTGRES_HOST=postgres.hostname or "127.0.0.1",
            POSTGRES_PORT=postgres.port or 5432,
            POSTGRES_DB=postgres.path.removeprefix("/"),
            POSTGRES_USER=postgres.username or "postgres",
            POSTGRES_PASSWORD=postgres.password or "",
        )
    )
    user_ids: list[UUID] = []
    database._tenant_test_user_ids = user_ids  # type: ignore[attr-defined]
    try:
        yield database
    finally:
        await cleanup_users(database, user_ids)
        await database.close()


async def cleanup_users(database: Database, user_ids: list[UUID]) -> None:
    if not user_ids:
        return
    async with database.sessions() as session, session.begin():
        interview_ids = select(InterviewSession.id).where(InterviewSession.user_id.in_(user_ids))
        voice_ids = select(VoiceInterviewSession.id).where(
            VoiceInterviewSession.user_id.in_(user_ids)
        )
        rag_ids = select(RagChatSession.id).where(RagChatSession.user_id.in_(user_ids))
        resume_ids = select(Resume.id).where(Resume.user_id.in_(user_ids))
        knowledge_base_ids = select(KnowledgeBase.id).where(KnowledgeBase.user_id.in_(user_ids))
        await session.execute(
            delete(VoiceInterviewMessage).where(VoiceInterviewMessage.session_id.in_(voice_ids))
        )
        await session.execute(
            delete(VoiceInterviewSession).where(VoiceInterviewSession.user_id.in_(user_ids))
        )
        await session.execute(
            delete(InterviewTurnRecord).where(
                InterviewTurnRecord.interview_session_id.in_(interview_ids)
            )
        )
        await session.execute(
            update(InterviewSession)
            .where(InterviewSession.user_id.in_(user_ids))
            .values(current_question_id=None)
        )
        await session.execute(
            delete(InterviewQuestionRecord).where(
                InterviewQuestionRecord.interview_session_id.in_(interview_ids)
            )
        )
        await session.execute(
            delete(InterviewSession).where(InterviewSession.user_id.in_(user_ids))
        )
        await session.execute(
            delete(RagSessionKnowledgeBase).where(RagSessionKnowledgeBase.session_id.in_(rag_ids))
        )
        await session.execute(delete(RagChatMessage).where(RagChatMessage.session_id.in_(rag_ids)))
        await session.execute(delete(RagChatSession).where(RagChatSession.user_id.in_(user_ids)))
        await session.execute(
            delete(KnowledgeBaseQuestion).where(
                KnowledgeBaseQuestion.knowledge_base_id.in_(knowledge_base_ids)
            )
        )
        await session.execute(
            delete(ResumeAnalysis).where(ResumeAnalysis.resume_id.in_(resume_ids))
        )
        await session.execute(delete(Resume).where(Resume.user_id.in_(user_ids)))
        await session.execute(delete(KnowledgeBase).where(KnowledgeBase.user_id.in_(user_ids)))
        await session.execute(
            delete(InterviewSchedule).where(InterviewSchedule.user_id.in_(user_ids))
        )
        await session.execute(delete(UserAccount).where(UserAccount.id.in_(user_ids)))


async def create_user(repository: AuthRepository, email: str) -> UserAccount:
    return await repository.create_human_user(
        email=email,
        display_name=email,
        password_hash="integration-placeholder-hash",
        role="USER",
        status="ACTIVE",
        now=utc_now(),
        email_verified=True,
    )


@pytest.mark.asyncio
async def test_root_repositories_hide_other_users_resources(
    tenant_database: Database,
) -> None:
    auth = AuthRepository(tenant_database.sessions)
    suffix = uuid4()
    user_a = await create_user(auth, f"tenant-a-{suffix}@example.test")
    user_b = await create_user(auth, f"tenant-b-{suffix}@example.test")
    user_ids = tenant_database._tenant_test_user_ids  # type: ignore[attr-defined]
    user_ids.extend((user_a.id, user_b.id))
    timestamp = datetime(2026, 8, 25, 12, 0)

    async with tenant_database.sessions() as session, session.begin():
        schedule_a = await InterviewScheduleRepository(session, user_a.id).add(
            InterviewSchedule(
                company_name="A",
                created_at=timestamp,
                interview_time=timestamp,
                interview_type=None,
                interviewer=None,
                meeting_link=None,
                notes=None,
                position="Engineer",
                round_number=None,
                status="PENDING",
                updated_at=timestamp,
                user_id=user_a.id,
            )
        )
        shared_resume_hash = f"{suffix.hex[:32]}a".ljust(64, "0")
        resume_a = await ResumeRepository(session, user_a.id).add(
            Resume(
                access_count=1,
                analyze_error=None,
                analyze_status="COMPLETED",
                content_type="text/plain",
                file_hash=shared_resume_hash,
                file_size=1,
                last_accessed_at=timestamp,
                original_filename="a.txt",
                resume_text="A resume",
                storage_key=None,
                storage_url=None,
                uploaded_at=timestamp,
                user_id=user_a.id,
            )
        )
        resume_b = await ResumeRepository(session, user_b.id).add(
            Resume(
                access_count=1,
                analyze_error=None,
                analyze_status="COMPLETED",
                analysis_provider_alias="dashscope",
                content_type="text/plain",
                file_hash=shared_resume_hash,
                file_size=1,
                last_accessed_at=timestamp,
                original_filename="b.txt",
                resume_text="B resume",
                storage_key=None,
                storage_url=None,
                uploaded_at=timestamp,
                user_id=user_b.id,
            )
        )
        shared_kb_hash = f"{suffix.hex[:32]}b".ljust(64, "0")
        knowledge_a = await KnowledgeBaseRepository(session, user_a.id).add(
            KnowledgeBase(
                access_count=1,
                category=None,
                chunk_count=0,
                content_type="text/plain",
                file_hash=shared_kb_hash,
                file_size=1,
                last_accessed_at=timestamp,
                name="A knowledge",
                original_filename="a-kb.txt",
                question_count=0,
                question_gen_status="NONE",
                question_gen_error=None,
                question_gen_task_id=None,
                question_gen_config=None,
                question_gen_message=None,
                question_gen_saved_count=0,
                question_gen_skipped_count=0,
                question_gen_updated_at=None,
                storage_key=None,
                storage_url=None,
                uploaded_at=timestamp,
                vector_error=None,
                vector_status="COMPLETED",
                user_id=user_a.id,
            )
        )
        knowledge_b = await KnowledgeBaseRepository(session, user_b.id).add(
            KnowledgeBase(
                access_count=1,
                category=None,
                chunk_count=0,
                content_type="text/plain",
                embedding_provider_alias="dashscope",
                file_hash=shared_kb_hash,
                file_size=1,
                last_accessed_at=timestamp,
                name="B knowledge",
                original_filename="b-kb.txt",
                question_count=0,
                question_gen_status="NONE",
                question_gen_error=None,
                question_gen_task_id=None,
                question_gen_config=None,
                question_gen_message=None,
                question_gen_saved_count=0,
                question_gen_skipped_count=0,
                question_gen_updated_at=None,
                question_provider_alias="dashscope",
                storage_key=None,
                storage_url=None,
                uploaded_at=timestamp,
                vector_error=None,
                vector_status="COMPLETED",
                user_id=user_b.id,
            )
        )

    interview_a = InterviewRepository(
        tenant_database.sessions,
        now=lambda: timestamp,
        user_id=user_a.id,
    )
    aggregate = await interview_a.create_session(
        session_id=str(uuid4()),
        channel=InterviewChannel.TEXT,
        resume_id=resume_a.id,
        questions=[PlannedInterviewQuestion(question="Question", type="GENERAL")],
        max_follow_ups_per_main=0,
        llm_provider=None,
        skill_id="java-backend",
        difficulty="mid",
        request_id=str(uuid4()),
    )
    rag_a = await RagChatRepository(
        tenant_database.sessions,
        now=lambda: timestamp,
        user_id=user_a.id,
    ).create_session([knowledge_a.id], "A chat")

    async with tenant_database.sessions() as session:
        assert await InterviewScheduleRepository(session, user_b.id).get(schedule_a.id) is None
        assert await ResumeRepository(session, user_b.id).get(resume_a.id) is None
        assert await KnowledgeBaseRepository(session, user_b.id).get(knowledge_a.id) is None
        assert await ResumeRepository(session, user_a.id).get(resume_b.id) is None
        assert await KnowledgeBaseRepository(session, user_a.id).get(knowledge_b.id) is None
    assert (
        await InterviewRepository(
            tenant_database.sessions,
            now=lambda: timestamp,
            user_id=user_b.id,
        ).find_session(aggregate.session.session_id)
        is None
    )
    with pytest.raises(BusinessException, match="会话不存在"):
        await RagChatRepository(
            tenant_database.sessions,
            now=lambda: timestamp,
            user_id=user_b.id,
        ).session_detail(rag_a.session.id)
