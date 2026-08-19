from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime
from pathlib import Path

from interview_guide.common.ai.prompts import PromptRepository
from interview_guide.common.ai.skills import SkillRepository
from interview_guide.common.ai.structured import StructuredOutputInvoker
from interview_guide.common.config.settings import get_settings
from interview_guide.common.infrastructure import RuntimeInfrastructure
from interview_guide.common.logging.config import configure_logging
from interview_guide.common.redis import RedisConnection
from interview_guide.common.redis.streams import (
    INTERVIEW_EVALUATE,
    KB_QUESTION_GEN,
    KB_VECTORIZE,
    RESUME_ANALYZE,
    STREAM_DEFINITIONS,
    VOICE_EVALUATE,
    RedisStreamService,
    SequentialStreamConsumer,
    run_stream_consumers,
)
from interview_guide.modules.interview.evaluation import (
    AnswerEvaluationService,
    UnifiedEvaluationService,
)
from interview_guide.modules.interview.question import InterviewSkillLibrary
from interview_guide.modules.interview.repository import InterviewRepository
from interview_guide.modules.interview.service import InterviewEvaluateHandler
from interview_guide.modules.knowledge_base.question_service import (
    KnowledgeBaseQuestionGenerationService,
    QuestionGenerationStateService,
    QuestionGenStreamHandler,
    QuestionGenStreamProducer,
)
from interview_guide.modules.knowledge_base.vectorization import (
    KnowledgeBaseVectorizationService,
    KnowledgeBaseVectorRepository,
    VectorizeStreamHandler,
)
from interview_guide.modules.resume.analysis import (
    ResumeAnalyzeHandler,
    ResumeGradingService,
)
from interview_guide.modules.voice_interview.evaluation import (
    VoiceEvaluateStreamHandler,
    VoiceInterviewEvaluationService,
)
from interview_guide.modules.voice_interview.repository import VoiceInterviewRepository
from interview_guide.modules.voice_interview.service import (
    VoiceEvaluationProducer,
    VoiceInterviewService,
)
from interview_guide.process import install_shutdown_handlers

logger = logging.getLogger(__name__)


async def run_worker(
    stop_event: asyncio.Event | None = None,
    redis_connection: RedisConnection | None = None,
) -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    resolved_stop_event = stop_event or asyncio.Event()
    if stop_event is None:
        install_shutdown_handlers(resolved_stop_event)
    connection = redis_connection or RedisConnection(settings)
    owns_connection = redis_connection is None
    infrastructure: RuntimeInfrastructure | None = None
    try:
        if owns_connection:
            infrastructure = RuntimeInfrastructure(settings)
            await infrastructure.start()
            streams = infrastructure.streams
        else:
            await connection.start()
            streams = RedisStreamService(connection.client)
        for definition in STREAM_DEFINITIONS:
            await streams.ensure_group(definition)
        logger.info("worker started streamCount=%s", len(STREAM_DEFINITIONS))
        if infrastructure is None:
            await resolved_stop_event.wait()
        else:
            resources = Path(__file__).resolve().parents[2] / "resources"
            grading = ResumeGradingService(
                infrastructure.provider_registry,
                StructuredOutputInvoker(infrastructure.llm_adapter),
                PromptRepository(resources),
            )
            now_factory = datetime.now
            resume_consumer = SequentialStreamConsumer(
                streams,
                RESUME_ANALYZE,
                f"{RESUME_ANALYZE.consumer_prefix}{str(uuid.uuid4())[:8]}",
                ResumeAnalyzeHandler(
                    infrastructure.database.sessions,
                    streams,
                    grading,
                    now_factory,
                ),
            )
            vector_repository = KnowledgeBaseVectorRepository(infrastructure.database.sessions)
            vector_consumer = SequentialStreamConsumer(
                streams,
                KB_VECTORIZE,
                f"{KB_VECTORIZE.consumer_prefix}{str(uuid.uuid4())[:8]}",
                VectorizeStreamHandler(
                    vector_repository,
                    streams,
                    KnowledgeBaseVectorizationService(
                        vector_repository,
                        infrastructure.provider_registry,
                        infrastructure.llm_adapter,
                    ),
                ),
            )
            question_generation_state = QuestionGenerationStateService(
                infrastructure.database.sessions,
                now=now_factory,
            )
            question_generation_producer = QuestionGenStreamProducer(
                streams,
                question_generation_state,
            )
            question_generation_consumer = SequentialStreamConsumer(
                streams,
                KB_QUESTION_GEN,
                f"{KB_QUESTION_GEN.consumer_prefix}{str(uuid.uuid4())[:8]}",
                QuestionGenStreamHandler(
                    question_generation_state,
                    question_generation_producer,
                    KnowledgeBaseQuestionGenerationService(
                        infrastructure.database.sessions,
                        infrastructure.provider_registry,
                        infrastructure.llm_adapter,
                        StructuredOutputInvoker(infrastructure.llm_adapter),
                        PromptRepository(resources),
                        infrastructure.prompt_sanitizer,
                        question_generation_state,
                        now=now_factory,
                    ),
                ),
            )
            skills = InterviewSkillLibrary(SkillRepository(resources), resources)
            unified_evaluation = UnifiedEvaluationService(
                StructuredOutputInvoker(infrastructure.llm_adapter),
                PromptRepository(resources),
                batch_size=settings.interview_evaluation_batch_size,
                tools=(skills.tool_definition(),),
            )
            interview_consumer = SequentialStreamConsumer(
                streams,
                INTERVIEW_EVALUATE,
                f"{INTERVIEW_EVALUATE.consumer_prefix}{str(uuid.uuid4())[:8]}",
                InterviewEvaluateHandler(
                    InterviewRepository(
                        infrastructure.database.sessions,
                        now=now_factory,
                    ),
                    streams,
                    AnswerEvaluationService(
                        unified_evaluation,
                        skills,
                    ),
                    infrastructure.provider_registry,
                ),
            )
            voice_repository = VoiceInterviewRepository(
                infrastructure.database.sessions,
                now_factory,
            )
            voice_producer = VoiceEvaluationProducer(
                streams,
                voice_repository,
                infrastructure.redis.client,
            )
            voice_service = VoiceInterviewService(
                voice_repository,
                infrastructure.redis.client,
                voice_producer,
                now_factory,
            )
            voice_consumer = SequentialStreamConsumer(
                streams,
                VOICE_EVALUATE,
                f"{VOICE_EVALUATE.consumer_prefix}{str(uuid.uuid4())[:8]}",
                VoiceEvaluateStreamHandler(
                    voice_repository,
                    streams,
                    VoiceInterviewEvaluationService(
                        voice_repository,
                        unified_evaluation,
                        infrastructure.provider_registry,
                        skills,
                        now_factory,
                    ),
                    voice_service,
                ),
            )
            await run_stream_consumers(
                (
                    resume_consumer,
                    vector_consumer,
                    question_generation_consumer,
                    interview_consumer,
                    voice_consumer,
                ),
                resolved_stop_event,
            )
    finally:
        if infrastructure is not None:
            await infrastructure.close()
        elif owns_connection:
            await connection.close()
        logger.info("worker stopped")


def main() -> None:
    asyncio.run(run_worker())
