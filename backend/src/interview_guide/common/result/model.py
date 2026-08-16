from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from interview_guide.common.errors.codes import ErrorCode


class Result[T](BaseModel):
    code: int
    data: T | None
    message: str
    success: bool

    @classmethod
    def ok(cls, data: T | None = None, message: str = "success") -> Result[T]:
        return cls(code=200, data=data, message=message, success=True)

    @classmethod
    def error(
        cls,
        error: ErrorCode | int,
        message: str | None = None,
    ) -> Result[Any]:
        if isinstance(error, ErrorCode):
            code = error.code
            resolved_message = message or error.message
        else:
            code = error
            resolved_message = message or "系统繁忙，请稍后重试"
        return Result[Any](
            code=code,
            data=None,
            message=resolved_message,
            success=False,
        )
