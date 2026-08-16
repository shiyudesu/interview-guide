from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from copy import deepcopy
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import JSONResponse, Response

from interview_guide.common.api.middleware import (
    CompatibilityCorsMiddleware,
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
from interview_guide.modules.interview_schedule.api import (
    router as interview_schedule_router,
)
from interview_guide.modules.interview_skill.api import (
    router as interview_skill_router,
)
from interview_guide.modules.llm_provider.api import router as llm_provider_router

ACTUATOR_MEDIA_TYPE = "application/vnd.spring-boot.actuator.v3+json"


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)
    metrics = ApplicationMetrics()
    blocking_executor = BlockingExecutor(resolved_settings.blocking_worker_count)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.accepting_tasks = True
        infrastructure: RuntimeInfrastructure | None = None
        try:
            if resolved_settings.infrastructure_startup_enabled:
                infrastructure = RuntimeInfrastructure(resolved_settings)
                await infrastructure.start()
                app.state.infrastructure = infrastructure
            yield
        finally:
            app.state.accepting_tasks = False
            if infrastructure is not None:
                await infrastructure.close()
            await blocking_executor.shutdown()

    app = FastAPI(
        title="智能 AI 面试官平台 API",
        description="简历分析、模拟面试、知识库管理 RESTful API 文档",
        version="1.0.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings
    app.state.metrics = metrics
    app.state.blocking_executor = blocking_executor

    install_exception_handlers(app)
    app.include_router(interview_schedule_router)
    app.include_router(interview_skill_router)
    app.include_router(llm_provider_router)
    app.add_middleware(
        RequestContextMiddleware,
        metrics=metrics,
    )
    app.add_middleware(
        CompatibilityCorsMiddleware,
        allowed_origins=resolved_settings.allowed_origins,
    )
    app.add_middleware(
        MultipartSizeLimitMiddleware,
        max_bytes=resolved_settings.multipart_max_bytes,
    )

    @app.get("/actuator/health", include_in_schema=False)
    async def actuator_health() -> JSONResponse:
        return JSONResponse(
            content={"groups": ["liveness", "readiness"], "status": "UP"},
            media_type=ACTUATOR_MEDIA_TYPE,
        )

    @app.get("/actuator/info", include_in_schema=False)
    async def actuator_info() -> JSONResponse:
        return JSONResponse(content={}, media_type=ACTUATOR_MEDIA_TYPE)

    @app.get("/actuator/metrics", include_in_schema=False)
    async def actuator_metrics() -> JSONResponse:
        return JSONResponse(
            content={"names": metrics.metric_names},
            media_type=ACTUATOR_MEDIA_TYPE,
        )

    @app.get("/actuator/prometheus", include_in_schema=False)
    async def actuator_prometheus() -> Response:
        return Response(
            content=metrics.render_prometheus(),
            media_type="text/plain;version=0.0.4;charset=utf-8",
        )

    @app.get("/v3/api-docs", include_in_schema=False)
    async def openapi_document(request: Request) -> JSONResponse:
        schema: dict[str, Any] = deepcopy(app.openapi())
        schema["servers"] = [
            {
                "url": str(request.base_url).rstrip("/"),
                "description": "Generated server url",
            }
        ]
        return JSONResponse(content=schema)

    @app.get("/swagger-ui.html", include_in_schema=False)
    async def swagger_ui() -> Response:
        return get_swagger_ui_html(
            openapi_url="/v3/api-docs",
            title="Swagger UI",
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
    )
