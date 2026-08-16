from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from starlette.responses import Response

from interview_guide.common.api.responses import result_response
from interview_guide.common.errors.codes import ErrorCode
from interview_guide.common.errors.exceptions import BusinessException
from interview_guide.common.result import Result

logger = logging.getLogger(__name__)


def validation_message(errors: Sequence[Any]) -> str:
    messages: list[str] = []
    for raw_error in errors:
        if not isinstance(raw_error, dict):
            messages.append(str(raw_error))
            continue
        error: dict[str, Any] = raw_error
        context = error.get("ctx") or {}
        context_error = context.get("error")
        if context_error is not None:
            messages.append(str(context_error))
        else:
            messages.append(str(error.get("msg", ErrorCode.BAD_REQUEST.message)))
    return ", ".join(messages)


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(BusinessException)
    async def handle_business_exception(
        request: Request,
        exception: BusinessException,
    ) -> Response:
        del request
        logger.warning(
            "business exception code=%s message=%s",
            exception.code,
            exception.message,
        )
        return result_response(Result.error(exception.code, exception.message))

    @app.exception_handler(RequestValidationError)
    async def handle_validation_exception(
        request: Request,
        exception: RequestValidationError,
    ) -> Response:
        del request
        if any(error.get("type") == "json_invalid" for error in exception.errors()):
            logger.exception("malformed JSON request", exc_info=exception)
            return result_response(Result.error(ErrorCode.INTERNAL_ERROR, "系统繁忙，请稍后重试"))
        message = validation_message(exception.errors())
        logger.warning("request validation failed message=%s", message)
        return result_response(Result.error(ErrorCode.BAD_REQUEST, message))

    @app.exception_handler(HTTPException)
    async def handle_http_exception(
        request: Request,
        exception: HTTPException,
    ) -> Response:
        if exception.status_code == 404:
            return result_response(Result.error(ErrorCode.NOT_FOUND, "API 接口不存在"))
        if exception.status_code == 405:
            return result_response(
                Result.error(
                    ErrorCode.METHOD_NOT_ALLOWED,
                    f"请求方法不支持: {request.method}",
                )
            )
        return result_response(
            Result.error(exception.status_code, str(exception.detail)),
            status_code=exception.status_code,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_exception(
        request: Request,
        exception: Exception,
    ) -> Response:
        del request
        logger.exception("unexpected application exception", exc_info=exception)
        return result_response(Result.error(ErrorCode.INTERNAL_ERROR, "系统繁忙，请稍后重试"))
