from __future__ import annotations

from interview_guide.common.errors.codes import ErrorCode


class BusinessException(Exception):
    def __init__(
        self,
        error_code: ErrorCode,
        message: str | None = None,
    ) -> None:
        self.code = error_code.code
        self.message = message or error_code.message
        super().__init__(self.message)
