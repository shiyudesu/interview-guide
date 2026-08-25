from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from interview_guide.common.api.middleware import (
    MultipartSizeLimitMiddleware,
    RequestContextMiddleware,
)
from interview_guide.common.config.settings import Settings, get_settings
from interview_guide.common.errors.handlers import install_exception_handlers
from interview_guide.common.infrastructure import RuntimeInfrastructure
from interview_guide.common.logging.config import configure_logging
from interview_guide.common.metrics import ApplicationMetrics
from interview_guide.common.runtime import BlockingExecutor
from interview_guide.common.telemetry import configure_tracing
from interview_guide.modules.auth.api import router as auth_router
from interview_guide.modules.auth.middleware import AuthenticationMiddleware
from interview_guide.modules.interview.api import router as interview_router
from interview_guide.modules.interview_schedule.api import (
    router as interview_schedule_router,
)
from interview_guide.modules.interview_skill.api import (
    router as interview_skill_router,
)
from interview_guide.modules.knowledge_base.api import (
    router as knowledge_base_router,
)
from interview_guide.modules.knowledge_base.interview_api import (
    router as knowledge_base_interview_router,
)
from interview_guide.modules.knowledge_base.rag_chat_api import (
    router as rag_chat_router,
)
from interview_guide.modules.llm_provider.api import router as llm_provider_router
from interview_guide.modules.resume.api import router as resume_router
from interview_guide.modules.voice_interview.api import (
    router as voice_interview_router,
)
from interview_guide.modules.voice_interview.runtime import (
    create_voice_websocket_runtime,
)
from interview_guide.modules.voice_interview.websocket_api import (
    router as voice_interview_websocket_router,
)


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)
    metrics = ApplicationMetrics()
    blocking_executor = BlockingExecutor(resolved_settings.blocking_worker_count)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.accepting_tasks = True
        infrastructure: RuntimeInfrastructure | None = None
        voice_runtime = None
        try:
            if resolved_settings.infrastructure_startup_enabled:
                infrastructure = RuntimeInfrastructure(
                    resolved_settings,
                    blocking_executor,
                )
                await infrastructure.start()
                app.state.infrastructure = infrastructure
                voice_runtime = create_voice_websocket_runtime(
                    infrastructure,
                    resolved_settings,
                    metrics,
                )
                app.state.voice_websocket_runtime = voice_runtime
            yield
        finally:
            app.state.accepting_tasks = False
            if voice_runtime is not None:
                await voice_runtime.close()
            if infrastructure is not None:
                await infrastructure.close()
            await blocking_executor.shutdown()

    app = FastAPI(
        title="智能 AI 面试官平台 API",
        description="简历分析、模拟面试、知识库管理 RESTful API 文档",
        version="1.0.0",
        docs_url="/docs",
        redoc_url=None,
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings
    app.state.metrics = metrics
    app.state.blocking_executor = blocking_executor

    install_exception_handlers(app)
    app.include_router(auth_router)
    app.include_router(interview_schedule_router)
    app.include_router(interview_router)
    app.include_router(interview_skill_router)
    app.include_router(llm_provider_router)
    app.include_router(resume_router)
    app.include_router(voice_interview_router)
    app.include_router(voice_interview_websocket_router)
    app.include_router(knowledge_base_router)
    app.include_router(knowledge_base_interview_router)
    app.include_router(rag_chat_router)
    app.add_middleware(
        RequestContextMiddleware,
        metrics=metrics,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(resolved_settings.allowed_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(
        MultipartSizeLimitMiddleware,
        max_bytes=resolved_settings.multipart_max_bytes,
    )
    app.add_middleware(
        AuthenticationMiddleware,
        settings=resolved_settings,
    )

    @app.get("/health", include_in_schema=False)
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/info", include_in_schema=False)
    async def info() -> dict[str, str]:
        return {"name": "interview-guide", "version": app.version}

    @app.get("/metrics", include_in_schema=False)
    async def prometheus_metrics() -> Response:
        return Response(
            content=metrics.render_prometheus(),
            media_type="text/plain;version=0.0.4;charset=utf-8",
        )

    configure_tracing(app, resolved_settings)
    return app


app = create_app()


def run() -> None:
    settings = get_settings()
    uvicorn.run(
        "interview_guide.main:app",
        host=settings.server_host,
        port=settings.server_port,
        workers=1,
        access_log=False,
        ws_max_size=2 * 1024 * 1024,
    )
