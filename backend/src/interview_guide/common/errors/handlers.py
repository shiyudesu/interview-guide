from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from starlette.responses import Response

from interview_guide.common.api.responses import problem_response
from interview_guide.common.errors.codes import ErrorCode
from interview_guide.common.errors.exceptions import BusinessException

logger = logging.getLogger(__name__)
MISSING_FIELD_MESSAGES = {
    "companyName": "公司名称不能为空",
    "company_name": "公司名称不能为空",
    "interviewTime": "面试时间不能为空",
    "interview_time": "面试时间不能为空",
    "knowledgeBaseIds": "至少选择一个知识库",
    "knowledge_base_ids": "至少选择一个知识库",
    "position": "岗位不能为空",
    "question": "问题不能为空",
    "rawText": "文本不能为空",
    "raw_text": "文本不能为空",
    "title": "标题不能为空",
}


def validation_message(errors: Sequence[Any]) -> str:
    messages: list[str] = []
    for raw_error in errors:
        if not isinstance(raw_error, dict):
            messages.append(str(raw_error))
            continue
        error: dict[str, Any] = raw_error
        if error.get("type") == "missing":
            location = error.get("loc") or ()
            field = str(location[-1]) if location else ""
            messages.append(
                MISSING_FIELD_MESSAGES.get(
                    field,
                    str(error.get("msg", ErrorCode.BAD_REQUEST.message)),
                )
            )
            continue
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
        return problem_response(exception.code, exception.message)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_exception(
        request: Request,
        exception: RequestValidationError,
    ) -> Response:
        del request
        if any(error.get("type") == "json_invalid" for error in exception.errors()):
            logger.warning("malformed JSON request")
            return problem_response(400, "请求体不是有效的 JSON", 400)
        message = validation_message(exception.errors())
        logger.warning("request validation failed message=%s", message)
        return problem_response(ErrorCode.BAD_REQUEST.code, message, 422)

    @app.exception_handler(HTTPException)
    async def handle_http_exception(
        request: Request,
        exception: HTTPException,
    ) -> Response:
        if exception.status_code == 404:
            return problem_response(ErrorCode.NOT_FOUND.code, "API 接口不存在", 404)
        if exception.status_code == 405:
            return problem_response(
                ErrorCode.METHOD_NOT_ALLOWED.code,
                f"请求方法不支持: {request.method}",
                405,
            )
        return problem_response(
            exception.status_code,
            str(exception.detail),
            exception.status_code,
        )

    @app.exception_handler(ValueError)
    async def handle_value_error(
        request: Request,
        exception: ValueError,
    ) -> Response:
        del request
        logger.warning("illegal argument message=%s", exception)
        return problem_response(ErrorCode.BAD_REQUEST.code, str(exception), 400)

    @app.exception_handler(Exception)
    async def handle_unexpected_exception(
        request: Request,
        exception: Exception,
    ) -> Response:
        del request
        logger.exception("unexpected application exception", exc_info=exception)
        return problem_response(ErrorCode.INTERNAL_ERROR.code, "服务器内部错误", 500)
