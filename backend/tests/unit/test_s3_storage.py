from __future__ import annotations

from typing import Any

import pytest
from botocore.exceptions import ClientError

from interview_guide.common.config.settings import Settings
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


def settings() -> Settings:
    return Settings(
        _env_file=None,
        APP_AI_CONFIG_ENCRYPTION_KEY="test-key",
        APP_STORAGE_ACCESS_KEY="access",
        APP_STORAGE_SECRET_KEY="secret",
        APP_STORAGE_AUTO_CREATE_BUCKET=False,
    )


@pytest.mark.asyncio
async def test_head_error_is_treated_as_missing_and_delete_is_skipped() -> None:
    executor = BlockingExecutor(max_workers=1)
    storage = S3Storage(
        settings(),
        executor,
        client=FailingHeadClient(),  # type: ignore[arg-type]
    )

    assert await storage.exists("missing") is False
    await storage.delete("missing")
    await executor.shutdown()
