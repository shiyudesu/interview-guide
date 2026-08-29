from __future__ import annotations

import logging
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import Body
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict

from interview_guide.common.api.middleware import request_log_level
from interview_guide.common.api.responses import result_response, serialized_result
from interview_guide.common.config.settings import Settings
from interview_guide.common.errors import BusinessException, ErrorCode
from interview_guide.common.result import Result
from interview_guide.main import create_app
from interview_guide.modules.interview.api import interview_service
from interview_guide.modules.resume.api import resume_service


def settings(**overrides: object) -> Settings:
    return Settings(
        _env_file=None,
        APP_AI_CONFIG_ENCRYPTION_KEY="test-encryption-key",
        APP_INFRASTRUCTURE_STARTUP_ENABLED=False,
        OTEL_ENABLED=False,
        **overrides,
    )


def test_native_health_response() -> None:
    app = create_app(settings())

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {"status": "ok"}


def test_public_auth_config_exposes_only_feature_switches() -> None:
    app = create_app(
        settings(
            APP_AUTH_ENABLED=True,
            APP_AUTH_REGISTRATION_ENABLED=False,
        )
    )

    with TestClient(app) as client:
        response = client.get("/api/auth/config")

    assert response.status_code == 200
    assert response.json() == {
        "authEnabled": True,
        "registrationEnabled": False,
        "competitionMode": False,
    }


def test_request_logging_keeps_normal_traffic_nonblocking_at_info_level() -> None:
    assert request_log_level(200, 0.1) == logging.DEBUG
    assert request_log_level(200, 1.0) == logging.INFO
    assert request_log_level(404, 0.1) == logging.INFO
    assert request_log_level(500, 0.1) == logging.WARNING


def test_native_cors_preflight() -> None:
    app = create_app(settings())

    with TestClient(app) as client:
        response = client.options(
            "/api/example",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "content-type",
            },
        )

    assert response.status_code == 200
    assert response.text == "OK"
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "GET" in response.headers["access-control-allow-methods"]
    assert "content-type" in response.headers["access-control-allow-headers"].lower()
    assert response.headers["access-control-allow-credentials"] == "true"
    assert "Origin" in response.headers.get("vary", "")


def test_business_and_routing_errors_use_http_statuses() -> None:
    app = create_app(settings())

    @app.get("/api/test/business")
    async def business_error() -> None:
        raise BusinessException(ErrorCode.INTERVIEW_SCHEDULE_NOT_FOUND, "面试日程不存在: 9")

    @app.get("/api/test/method")
    async def get_only() -> dict[str, bool]:
        return {"ok": True}

    with TestClient(app) as client:
        business = client.get("/api/test/business")
        missing = client.get("/api/test/missing")
        method = client.post("/api/test/method")

    assert business.json() == {
        "code": 9001,
        "detail": "面试日程不存在: 9",
    }
    assert business.status_code == 404
    assert missing.json()["detail"] == "API 接口不存在"
    assert missing.status_code == 404
    assert method.json()["detail"] == "请求方法不支持: POST"
    assert method.status_code == 405


def test_unmatched_routes_share_a_bounded_metrics_label() -> None:
    app = create_app(settings())

    with TestClient(app) as client:
        client.get("/random-not-found-one")
        client.get("/random-not-found-two")
        metrics = client.get("/metrics").text

    assert 'pathTemplate="__unmatched__",status="404"' in metrics
    assert "random-not-found-one" not in metrics
    assert "random-not-found-two" not in metrics


def test_pdf_exports_preserve_standard_business_errors() -> None:
    class MissingInterviewExport:
        async def export_pdf(self, session_id: str) -> tuple[bytes, dict[str, str]]:
            del session_id
            raise BusinessException(ErrorCode.INTERVIEW_SESSION_NOT_FOUND)

    class MissingResumeExport:
        async def export_pdf(self, resume_id: int) -> tuple[bytes, dict[str, str]]:
            del resume_id
            raise BusinessException(ErrorCode.RESUME_NOT_FOUND)

    app = create_app(settings())
    app.dependency_overrides[interview_service] = MissingInterviewExport
    app.dependency_overrides[resume_service] = MissingResumeExport

    with TestClient(app) as client:
        interview = client.get("/api/interview/sessions/missing/export")
        resume = client.get("/api/resumes/999/export")

    assert interview.status_code == 404
    assert interview.json() == {"code": 3001, "detail": "面试会话不存在"}
    assert resume.status_code == 404
    assert resume.json() == {"code": 2001, "detail": "简历不存在"}


def test_interview_list_supports_bounded_backward_compatible_paging() -> None:
    class CapturingInterviewList:
        def __init__(self) -> None:
            self.arguments: dict[str, object] = {}

        async def list_sessions(self, **arguments: object) -> list[object]:
            self.arguments = arguments
            return []

    service = CapturingInterviewList()
    app = create_app(settings())
    app.dependency_overrides[interview_service] = lambda: service

    with TestClient(app) as client:
        response = client.get(
            "/api/interview/sessions",
            params=[
                ("sessionIds", "session-one"),
                ("sessionIds", "session-two"),
                ("limit", "20"),
                ("offset", "5"),
            ],
        )
        invalid = client.get("/api/interview/sessions?limit=201")

    assert response.status_code == 200
    assert response.json() == []
    assert service.arguments == {
        "session_ids": ["session-one", "session-two"],
        "limit": 20,
        "offset": 5,
    }
    assert invalid.status_code == 422
    assert set(invalid.json()) == {"code", "detail"}


class Payload(BaseModel):
    company_name: str


class ResponsePayload(BaseModel):
    model_config = ConfigDict(
        alias_generator=lambda value: value.replace("_name", "Name"),
        populate_by_name=True,
    )

    company_name: str
    created_at: datetime
    identifier: UUID
    optional: str | None


def test_result_adapter_returns_direct_json_data() -> None:
    result = Result.ok(
        ResponsePayload(
            company_name="示例公司",
            created_at=datetime(2026, 8, 16, 8, 0),
            identifier=UUID("11111111-1111-1111-1111-111111111111"),
            optional=None,
        )
    )
    response = result_response(result)

    assert response.headers["content-type"] == "application/json"
    expected = (
        b'{"companyName":"' + "示例公司".encode() + b'","created_at":"2026-08-16T08:00:00",'
        b'"identifier":"11111111-1111-1111-1111-111111111111","optional":null}'
    )
    assert serialized_result(result) == expected
    assert response.body == expected


def test_malformed_json_returns_bad_request() -> None:
    app = create_app(settings())

    @app.post("/api/test/json")
    async def parse_json(payload: Annotated[Payload, Body()]) -> Payload:
        return payload

    with TestClient(app) as client:
        response = client.post(
            "/api/test/json",
            content='{"company_name":',
            headers={"Content-Type": "application/json"},
        )

    assert response.status_code == 400
    assert response.json() == {
        "code": 400,
        "detail": "请求体不是有效的 JSON",
    }


def test_multipart_limit_returns_business_error() -> None:
    app = create_app(settings(APP_MULTIPART_MAX_BYTES=4))

    @app.post("/api/test/upload")
    async def upload() -> dict[str, bool]:
        return {"ok": True}

    with TestClient(app) as client:
        response = client.post(
            "/api/test/upload",
            files={"file": ("sample.txt", b"too large", "text/plain")},
        )

    assert response.status_code == 413
    assert response.json()["detail"] == "文件大小超过限制"


def test_native_openapi_and_docs_paths() -> None:
    app = create_app(settings())

    with TestClient(app, base_url="http://comparison:28080") as client:
        response = client.get("/openapi.json")
        docs = client.get("/docs")

    document = response.json()
    assert docs.status_code == 200
    assert "/api/interview/sessions/{session_id}/turns" in document["paths"]
    assert "/api/interview/sessions/{session_id}/answers" not in document["paths"]
    sessions = document["paths"]["/api/interview/sessions"]
    assert sessions["post"]["responses"]["201"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/InterviewSessionDTO"
    }
    turn = document["paths"]["/api/interview/sessions/{session_id}/turns"]["post"]
    assert turn["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/SubmitTurnResponse"
    }
    assert turn["responses"]["422"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ApiProblem"
    }
    delete = document["paths"]["/api/interview/sessions/{session_id}"]["delete"]
    assert set(delete["responses"]) >= {"204", "404"}
    resume_detail = document["components"]["schemas"]["ResumeDetailResponse"]
    assert resume_detail["properties"]["analyses"]["items"] == {
        "$ref": "#/components/schemas/ResumeAnalysisHistoryResponse"
    }
    assert resume_detail["properties"]["interviews"]["items"] == {
        "$ref": "#/components/schemas/ResumeInterviewResponse"
    }
    create_schema = document["components"]["schemas"][
        "interview_guide__modules__interview__models__CreateInterviewRequest"
    ]
    assert create_schema["properties"]["questionCount"] == {
        "type": "integer",
        "maximum": 30.0,
        "minimum": 1.0,
        "title": "Questioncount",
        "default": 8,
    }
