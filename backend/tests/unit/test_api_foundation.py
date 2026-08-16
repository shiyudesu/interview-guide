from __future__ import annotations

from typing import Annotated

from fastapi import Body
from fastapi.testclient import TestClient
from pydantic import BaseModel

from interview_guide.common.config.settings import Settings
from interview_guide.common.errors import BusinessException, ErrorCode
from interview_guide.main import ACTUATOR_MEDIA_TYPE, create_app


def settings(**overrides: object) -> Settings:
    return Settings(
        _env_file=None,
        APP_AI_CONFIG_ENCRYPTION_KEY="test-encryption-key",
        OTEL_ENABLED=False,
        **overrides,
    )


def test_health_response_matches_java_contract() -> None:
    app = create_app(settings())

    with TestClient(app) as client:
        response = client.get("/actuator/health")

    assert response.status_code == 200
    assert response.headers["content-type"] == ACTUATOR_MEDIA_TYPE
    assert response.content == b'{"groups":["liveness","readiness"],"status":"UP"}'


def test_cors_preflight_matches_java_headers() -> None:
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
    assert response.content == b""
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert response.headers["access-control-allow-methods"] == ("GET,POST,PUT,DELETE,PATCH,OPTIONS")
    assert response.headers["access-control-allow-headers"] == "content-type"
    assert response.headers["access-control-allow-credentials"] == "true"
    assert response.headers.get_list("vary") == [
        "Origin",
        "Access-Control-Request-Method",
        "Access-Control-Request-Headers",
    ]


def test_business_and_routing_errors_keep_http_200() -> None:
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
        "data": None,
        "message": "面试日程不存在: 9",
        "success": False,
    }
    assert business.status_code == 200
    assert missing.json()["message"] == "API 接口不存在"
    assert missing.status_code == 200
    assert method.json()["message"] == "请求方法不支持: POST"
    assert method.status_code == 200


class Payload(BaseModel):
    company_name: str


def test_malformed_json_matches_java_internal_error() -> None:
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

    assert response.status_code == 200
    assert response.json() == {
        "code": 500,
        "data": None,
        "message": "系统繁忙，请稍后重试",
        "success": False,
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

    assert response.status_code == 200
    assert response.json()["message"] == "文件大小超过限制"


def test_openapi_metadata_and_dynamic_server_url() -> None:
    app = create_app(settings())

    with TestClient(app, base_url="http://comparison:28080") as client:
        response = client.get("/v3/api-docs")

    document = response.json()
    assert document["info"] == {
        "title": "智能 AI 面试官平台 API",
        "description": "简历分析、模拟面试、知识库管理 RESTful API 文档",
        "version": "1.0.0",
    }
    assert document["servers"] == [
        {
            "url": "http://comparison:28080",
            "description": "Generated server url",
        }
    ]
