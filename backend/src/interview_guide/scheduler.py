from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import-untyped]

from interview_guide.common.config.settings import get_settings
from interview_guide.common.infrastructure import RuntimeInfrastructure
from interview_guide.common.logging.config import configure_logging
from interview_guide.modules.interview_schedule.service import (
    InterviewScheduleService,
    schedule_now,
)
from interview_guide.modules.knowledge_base.question_service import (
    QuestionGenerationRecoveryService,
    QuestionGenerationStateService,
    QuestionGenStreamProducer,
)
from interview_guide.modules.voice_interview.repository import VoiceInterviewRepository
from interview_guide.modules.voice_interview.service import (
    VoiceEvaluationProducer,
    VoiceInterviewService,
)
from interview_guide.process import install_shutdown_handlers

logger = logging.getLogger(__name__)


async def run_scheduler(stop_event: asyncio.Event | None = None) -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    resolved_stop_event = stop_event or asyncio.Event()
    if stop_event is None:
        install_shutdown_handlers(resolved_stop_event)
    scheduler = AsyncIOScheduler(timezone=settings.timezone)
    infrastructure: RuntimeInfrastructure | None = None
    try:
        if settings.infrastructure_startup_enabled:
            infrastructure = RuntimeInfrastructure(settings)
            await infrastructure.start()
            if settings.migration_fixed_time:
                fixed_now = datetime.fromisoformat(settings.migration_fixed_time)

                def now_factory() -> datetime:
                    return fixed_now
            else:
                now_factory = datetime.now

            async def expire_interview_schedules() -> None:
                assert infrastructure is not None
                async with infrastructure.database.sessions() as session:
                    updated = await InterviewScheduleService(
                        session,
                        now=lambda: schedule_now(settings),
                    ).expire_pending()
                    if updated:
                        logger.info(
                            "expired interview schedules updated=%s",
                            updated,
                        )

            state = QuestionGenerationStateService(
                infrastructure.database.sessions,
                now=now_factory,
            )
            recovery = QuestionGenerationRecoveryService(
                state,
                QuestionGenStreamProducer(infrastructure.streams, state),
                now=now_factory,
            )

            async def recover_question_generation() -> None:
                await recovery.recover()

            voice_repository = VoiceInterviewRepository(
                infrastructure.database.sessions,
                now_factory,
            )
            voice_service = VoiceInterviewService(
                voice_repository,
                infrastructure.redis.client,
                VoiceEvaluationProducer(
                    infrastructure.streams,
                    voice_repository,
                    infrastructure.redis.client,
                ),
                now_factory,
            )

            async def recover_voice_interviews() -> None:
                cleaned = await voice_service.cleanup_stale_sessions()
                if cleaned:
                    logger.info(
                        "recovered stale voice interviews updated=%s",
                        cleaned,
                    )

            scheduler.add_job(
                expire_interview_schedules,
                trigger="cron",
                minute=0,
                second=0,
                id="interview-schedule-expiry",
                max_instances=1,
                coalesce=False,
            )
            scheduler.add_job(
                recover_question_generation,
                trigger="interval",
                seconds=60,
                id="knowledge-base-question-generation-recovery",
                max_instances=1,
                coalesce=False,
            )
            scheduler.add_job(
                recover_voice_interviews,
                trigger="interval",
                seconds=60,
                id="voice-interview-recovery",
                max_instances=1,
                coalesce=False,
            )
        scheduler.start()
        logger.info(
            "scheduler started jobCount=%s",
            len(scheduler.get_jobs()),
        )
        await resolved_stop_event.wait()
    finally:
        scheduler.shutdown(wait=True)
        if infrastructure is not None:
            await infrastructure.close()
        logger.info("scheduler stopped")


def main() -> None:
    asyncio.run(run_scheduler())
