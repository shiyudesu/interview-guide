from __future__ import annotations

from typing import Any

import pytest
from botocore.exceptions import ClientError

from interview_guide.common.config.settings import Settings
from interview_guide.common.errors import BusinessException
from interview_guide.common.runtime import BlockingExecutor
from interview_guide.infrastructure.storage.s3 import S3Storage


class FailingHeadClient:
    def head_object(self, **arguments: Any) -> None:
        del arguments
        raise ClientError(
            {
                "Error": {"Code": "InternalError", "Message": "failed"},
                "ResponseMetadata": {"HTTPStatusCode": 500},
            },
            "HeadObject",
        )


class MissingHeadClient:
    def head_object(self, **arguments: Any) -> None:
        del arguments
        raise ClientError(
            {
                "Error": {"Code": "NoSuchKey", "Message": "missing"},
                "ResponseMetadata": {"HTTPStatusCode": 404},
            },
            "HeadObject",
        )


class RecordingDeleteClient:
    def __init__(self) -> None:
        self.deleted: list[str] = []

    def delete_object(self, **arguments: Any) -> None:
        self.deleted.append(str(arguments["Key"]))


def settings() -> Settings:
    return Settings(
        _env_file=None,
        APP_AI_CONFIG_ENCRYPTION_KEY="test-key",
        APP_STORAGE_ACCESS_KEY="access",
        APP_STORAGE_SECRET_KEY="secret",
        APP_STORAGE_AUTO_CREATE_BUCKET=False,
    )


@pytest.mark.asyncio
async def test_only_not_found_head_response_is_treated_as_missing() -> None:
    executor = BlockingExecutor(max_workers=1)
    try:
        missing = S3Storage(
            settings(),
            executor,
            client=MissingHeadClient(),  # type: ignore[arg-type]
        )
        failing = S3Storage(
            settings(),
            executor,
            client=FailingHeadClient(),  # type: ignore[arg-type]
        )

        assert await missing.exists("missing") is False
        with pytest.raises(BusinessException, match="检查文件状态失败"):
            await failing.exists("unavailable")
    finally:
        await executor.shutdown()


@pytest.mark.asyncio
async def test_delete_is_idempotent_without_a_racy_head_request() -> None:
    executor = BlockingExecutor(max_workers=1)
    client = RecordingDeleteClient()
    storage = S3Storage(
        settings(),
        executor,
        client=client,  # type: ignore[arg-type]
    )
    try:
        await storage.delete("resumes/example.pdf")
        await storage.delete(None)
        assert client.deleted == ["resumes/example.pdf"]
    finally:
        await executor.shutdown()
