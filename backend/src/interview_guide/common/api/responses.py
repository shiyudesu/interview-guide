from __future__ import annotations

from typing import Any

from fastapi.encoders import jsonable_encoder
from starlette.responses import JSONResponse

from interview_guide.common.result import Result


def result_response(result: Result[Any], *, status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        content=jsonable_encoder(
            result,
            by_alias=True,
            exclude_none=False,
        ),
        status_code=status_code,
    )
