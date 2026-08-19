from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
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
from interview_guide.main import MANAGEMENT_MEDIA_TYPE, create_app


def settings(**overrides: object) -> Settings:
    return Settings(
        _env_file=None,
        APP_AI_CONFIG_ENCRYPTION_KEY="test-encryption-key",
        APP_INFRASTRUCTURE_STARTUP_ENABLED=False,
        OTEL_ENABLED=False,
        **overrides,
    )


def test_health_response_matches_compatibility_contract() -> None:
    app = create_app(settings())

    with TestClient(app) as client:
        response = client.get("/actuator/health")

    assert response.status_code == 200
    assert response.headers["content-type"] == MANAGEMENT_MEDIA_TYPE
    assert response.content == b'{"groups":["liveness","readiness"],"status":"UP"}'


def test_request_logging_keeps_normal_traffic_nonblocking_at_info_level() -> None:
    assert request_log_level(200, 0.1) == logging.DEBUG
    assert request_log_level(200, 1.0) == logging.INFO
    assert request_log_level(404, 0.1) == logging.INFO
    assert request_log_level(500, 0.1) == logging.WARNING


def test_cors_preflight_matches_compatibility_headers() -> None:
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


class ResponsePayload(BaseModel):
    model_config = ConfigDict(
        alias_generator=lambda value: value.replace("_name", "Name"),
        populate_by_name=True,
    )

    company_name: str
    created_at: datetime
    identifier: UUID
    optional: str | None


def test_result_response_preserves_compact_compatibility_json() -> None:
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
        b'{"code":200,"data":{"companyName":"'
        + "示例公司".encode()
        + b'","created_at":"2026-08-16T08:00:00",'
        b'"identifier":"11111111-1111-1111-1111-111111111111","optional":null},'
        b'"message":"success","success":true}'
    )
    assert serialized_result(result) == expected
    assert response.body == expected


def test_malformed_json_matches_compatibility_internal_error() -> None:
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

    baseline_path = (
        Path(__file__).resolve().parents[2] / "resources/contracts/http-compatibility-baseline.json"
    )
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    openapi_case = next(case for case in baseline["cases"] if case["id"] == "openapi")
    document = json.loads(openapi_case["response"]["body"])
    document["servers"] = [
        {
            "url": "http://comparison:28080",
            "description": "Generated server url",
        }
    ]
    assert (
        response.content
        == json.dumps(
            document,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode()
    )
