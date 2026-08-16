from __future__ import annotations

from collections.abc import Callable, Sequence

from interview_guide.common.api.models import java_utf16_length
from interview_guide.common.errors import BusinessException, ErrorCode

RESUME_MAX_BYTES = 10 * 1024 * 1024
KNOWLEDGE_BASE_MAX_BYTES = 50 * 1024 * 1024
DOCUMENT_MAX_UTF16_UNITS = 5 * 1024 * 1024


def validate_file(data: bytes, max_size_bytes: int, file_type_name: str) -> None:
    if not data:
        raise BusinessException(
            ErrorCode.BAD_REQUEST,
            f"请选择要上传的{file_type_name}文件",
        )
    if len(data) > max_size_bytes:
        raise BusinessException(ErrorCode.BAD_REQUEST, "文件大小超过限制")


def is_allowed_type(
    content_type: str | None,
    allowed_types: Sequence[str],
) -> bool:
    if content_type is None or not allowed_types:
        return False
    normalized = content_type.lower()
    return any(
        normalized in allowed.lower() or allowed.lower() in normalized for allowed in allowed_types
    )


def validate_content_type_by_list(
    content_type: str | None,
    allowed_types: Sequence[str],
    error_message: str | None = None,
) -> None:
    if not is_allowed_type(content_type, allowed_types):
        raise BusinessException(
            ErrorCode.BAD_REQUEST,
            error_message or f"不支持的文件类型: {content_type}",
        )


def validate_content_type(
    content_type: str | None,
    filename: str | None,
    mime_type_checker: Callable[[str | None], bool],
    extension_checker: Callable[[str], bool],
    error_message: str | None = None,
) -> None:
    if mime_type_checker(content_type):
        return
    if filename is not None and extension_checker(filename):
        return
    raise BusinessException(
        ErrorCode.BAD_REQUEST,
        error_message or f"不支持的文件类型: {content_type}",
    )


def is_markdown_extension(filename: str | None) -> bool:
    if filename is None:
        return False
    normalized = filename.lower()
    return normalized.endswith((".md", ".markdown", ".mdown"))


def is_knowledge_base_mime_type(content_type: str | None) -> bool:
    if content_type is None:
        return False
    normalized = content_type.lower()
    return any(
        marker in normalized
        for marker in (
            "pdf",
            "msword",
            "wordprocessingml",
            "text/plain",
            "text/markdown",
            "text/x-markdown",
            "text/x-web-markdown",
            "application/rtf",
        )
    )


def validate_document_character_limit(text: str) -> None:
    if java_utf16_length(text) > DOCUMENT_MAX_UTF16_UNITS:
        raise BusinessException(
            ErrorCode.BAD_REQUEST,
            "文档内容超过最大字符限制",
        )
