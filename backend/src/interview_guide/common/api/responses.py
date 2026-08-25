from __future__ import annotations

import json
from typing import Any

from fastapi.encoders import jsonable_encoder
from starlette.responses import JSONResponse, Response

from interview_guide.common.api.models import ApiProblem
from interview_guide.common.result import Result

NOT_FOUND_CODES = {2001, 2008, 3001, 3003, 6001, 9001, 10001, 10006, 11001, 11008}
CONFLICT_CODES = {2004, 3004, 3007, 11002, 11007, 12002}
UNPROCESSABLE_CODES = {2002, 2006, 3009, 6002}
SERVICE_UNAVAILABLE_CODES = {2007, 3005, 3006, 6004, 6006, 7001, 7003, 11006, 11011}
INTERNAL_CODES = {2003, 3008, 4001, 4002, 4003, 5001, 6005, 11004, 11005, 11009, 11010}
STANDARD_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    status: {"model": ApiProblem}
    for status in (400, 401, 403, 404, 405, 409, 410, 422, 429, 500, 503, 504)
}


def http_status_for_code(code: int) -> int:
    if 400 <= code <= 599:
        return code
    if code in NOT_FOUND_CODES:
        return 404
    if code in CONFLICT_CODES:
        return 409
    if code == 3002:
        return 410
    if code in UNPROCESSABLE_CODES:
        return 422
    if code == 7002:
        return 504
    if code in SERVICE_UNAVAILABLE_CODES:
        return 503
    if code == 7004:
        return 401
    if code in {12001, 12004}:
        return 401
    if code in {12003, 12005, 12006}:
        return 403
    if code in {7005, 8001}:
        return 429
    if code in INTERNAL_CODES:
        return 500
    return 400


def problem_content(code: int, detail: str) -> dict[str, object]:
    return {"code": code, "detail": detail}


def problem_response(code: int, detail: str, status_code: int | None = None) -> JSONResponse:
    return JSONResponse(
        content=problem_content(code, detail),
        status_code=status_code or http_status_for_code(code),
    )


def serialized_result(result: Result[Any]) -> bytes:
    content = (
        jsonable_encoder(result.data)
        if result.success
        else problem_content(result.code, result.message)
    )
    return json.dumps(
        content,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")


def serialized_result_response(content: bytes, *, status_code: int = 200) -> Response:
    return Response(
        content=content,
        media_type="application/json",
        status_code=status_code,
    )


def result_response(result: Result[Any], *, status_code: int | None = None) -> Response:
    if not result.success:
        return problem_response(result.code, result.message, status_code)
    resolved_status = status_code or (204 if result.data is None else 200)
    if result.data is None:
        return Response(status_code=resolved_status)
    return JSONResponse(
        content=jsonable_encoder(result.data),
        status_code=resolved_status,
    )
