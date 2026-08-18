from __future__ import annotations

import os
import uuid
from datetime import datetime

import pytest

from interview_guide.common.config.settings import Settings
from interview_guide.common.runtime import BlockingExecutor
from interview_guide.infrastructure.storage.keys import FileKeyGenerator
from interview_guide.infrastructure.storage.s3 import S3Storage

S3_ENDPOINT = os.getenv("TEST_S3_ENDPOINT")
S3_ACCESS_KEY = os.getenv("TEST_S3_ACCESS_KEY", "minioadmin")
S3_SECRET_KEY = os.getenv("TEST_S3_SECRET_KEY", "minioadmin")
S3_BUCKET = os.getenv("TEST_S3_BUCKET", "interview-guide-integration")
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(S3_ENDPOINT is None, reason="TEST_S3_ENDPOINT is not configured"),
]


@pytest.mark.asyncio
async def test_s3_path_style_upload_head_download_and_delete() -> None:
    assert S3_ENDPOINT is not None
    settings = Settings(
        _env_file=None,
        APP_AI_CONFIG_ENCRYPTION_KEY="integration-key",
        APP_STORAGE_ENDPOINT=S3_ENDPOINT,
        APP_STORAGE_ACCESS_KEY=S3_ACCESS_KEY,
        APP_STORAGE_SECRET_KEY=S3_SECRET_KEY,
        APP_STORAGE_BUCKET=S3_BUCKET,
        APP_STORAGE_AUTO_CREATE_BUCKET=True,
    )
    executor = BlockingExecutor(max_workers=2)
    storage = S3Storage(
        settings,
        executor,
        key_generator=FileKeyGenerator(
            now=lambda: datetime(2026, 8, 16, 8, 0),
            uuid_factory=lambda: uuid.UUID("12345678-0000-0000-0000-000000000000"),
        ),
    )
    await storage.start()

    key = await storage.upload(
        b"fixed storage content",
        "测试.txt",
        "text/plain; charset=utf-8",
        "knowledgebases",
    )

    assert key == "knowledgebases/2026/08/16/12345678_CeShi.txt"
    assert await storage.exists(key)
    stat = await storage.stat(key)
    assert stat.content_length == len(b"fixed storage content")
    assert stat.content_type == "text/plain; charset=utf-8"
    assert await storage.download(key) == b"fixed storage content"
    assert storage.object_url(key) == (f"{S3_ENDPOINT}/{S3_BUCKET}/{key}")

    await storage.delete(key)
    assert not await storage.exists(key)
    await executor.shutdown()
