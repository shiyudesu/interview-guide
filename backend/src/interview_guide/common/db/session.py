from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from interview_guide.common.config.settings import Settings


class Database:
    def __init__(self, settings: Settings) -> None:
        self.engine: AsyncEngine = create_async_engine(
            settings.sqlalchemy_url,
            max_overflow=settings.database_max_overflow,
            pool_size=settings.database_pool_size,
        )
        self.sessions = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def close(self) -> None:
        await self.engine.dispose()
