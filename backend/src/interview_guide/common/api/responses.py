from __future__ import annotations

from typing import Any

from starlette.responses import Response

from interview_guide.common.result import Result


def serialized_result(result: Result[Any]) -> bytes:
    return result.model_dump_json(
        by_alias=True,
        exclude_none=False,
    ).encode("utf-8")


def serialized_result_response(content: bytes, *, status_code: int = 200) -> Response:
    return Response(
        content=content,
        media_type="application/json",
        status_code=status_code,
    )


def result_response(result: Result[Any], *, status_code: int = 200) -> Response:
    return serialized_result_response(
        serialized_result(result),
        status_code=status_code,
    )
