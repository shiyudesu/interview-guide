from __future__ import annotations

import os
from datetime import datetime
from urllib.parse import urlsplit

import pytest
from sqlalchemy import delete, select

from interview_guide.common.config.settings import Settings
from interview_guide.common.db.models import InterviewSchedule
from interview_guide.common.db.session import Database
from interview_guide.modules.interview_schedule.service import (
    InterviewScheduleService,
)

POSTGRES_URL = os.getenv("TEST_POSTGRES_URL")
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        POSTGRES_URL is None,
        reason="TEST_POSTGRES_URL is required",
    ),
]


@pytest.mark.asyncio
async def test_scheduler_expiry_updates_only_past_pending_rows() -> None:
    assert POSTGRES_URL is not None
    parsed = urlsplit(POSTGRES_URL)
    settings = Settings(
        _env_file=None,
        APP_AI_CONFIG_ENCRYPTION_KEY="integration-key",
        POSTGRES_HOST=parsed.hostname or "127.0.0.1",
        POSTGRES_PORT=parsed.port or 5432,
        POSTGRES_DB=parsed.path.removeprefix("/"),
        POSTGRES_USER=parsed.username or "postgres",
        POSTGRES_PASSWORD=parsed.password or "",
    )
    database = Database(settings)
    async with database.sessions() as session, session.begin():
        await session.execute(delete(InterviewSchedule))
        session.add_all(
            [
                InterviewSchedule(
                    company_name="Past",
                    position="Engineer",
                    interview_time=datetime(2026, 8, 15, 8, 0),
                    status="PENDING",
                ),
                InterviewSchedule(
                    company_name="Future",
                    position="Engineer",
                    interview_time=datetime(2026, 8, 17, 8, 0),
                    status="PENDING",
                ),
                InterviewSchedule(
                    company_name="Completed",
                    position="Engineer",
                    interview_time=datetime(2026, 8, 15, 8, 0),
                    status="COMPLETED",
                ),
            ]
        )

    async with database.sessions() as session:
        updated = await InterviewScheduleService(
            session,
            now=lambda: datetime(2026, 8, 16, 8, 0),
        ).expire_pending()
    assert updated == 1

    async with database.sessions() as session:
        rows = list(await session.scalars(select(InterviewSchedule).order_by(InterviewSchedule.id)))
    assert [row.status for row in rows] == [
        "CANCELLED",
        "PENDING",
        "COMPLETED",
    ]
    await database.close()
