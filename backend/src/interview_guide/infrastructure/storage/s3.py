from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from interview_guide.common.config.settings import Settings
from interview_guide.common.errors import BusinessException, ErrorCode
from interview_guide.common.runtime import BlockingExecutor
from interview_guide.infrastructure.storage.keys import FileKeyGenerator

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client


@dataclass(frozen=True)
class StoredObject:
    key: str
    content_type: str | None
    content_length: int


def create_s3_client(settings: Settings) -> S3Client:
    return boto3.client(
        "s3",
        endpoint_url=settings.storage_endpoint,
        aws_access_key_id=settings.storage_access_key.get_secret_value(),
        aws_secret_access_key=settings.storage_secret_key.get_secret_value(),
        region_name=settings.storage_region,
        config=Config(
            connect_timeout=settings.storage_api_call_attempt_timeout_seconds,
            read_timeout=settings.storage_api_call_attempt_timeout_seconds,
            retries={"mode": "standard", "total_max_attempts": 3},
            s3={"addressing_style": "path"},
        ),
    )


class S3Storage:
    def __init__(
        self,
        settings: Settings,
        executor: BlockingExecutor,
        client: S3Client | None = None,
        key_generator: FileKeyGenerator | None = None,
    ) -> None:
        self._settings = settings
        self._executor = executor
        self._client = client or create_s3_client(settings)
        self._keys = key_generator or FileKeyGenerator()

    async def start(self) -> None:
        if self._settings.storage_auto_create_bucket:
            await self.ensure_bucket_exists()

    async def ensure_bucket_exists(self) -> None:
        try:
            await self._call(self._client.head_bucket, Bucket=self._settings.storage_bucket)
        except ClientError as error:
            status = self._status_code(error)
            if status != 404:
                raise BusinessException(
                    ErrorCode.STORAGE_UPLOAD_FAILED,
                    f"检查存储桶失败: {error}",
                ) from error
            await self._create_bucket()
        except BotoCoreError as error:
            raise BusinessException(
                ErrorCode.STORAGE_UPLOAD_FAILED,
                f"检查存储桶失败: {error}",
            ) from error

    async def _create_bucket(self) -> None:
        try:
            await self._call(
                self._client.create_bucket,
                Bucket=self._settings.storage_bucket,
            )
        except ClientError as error:
            if self._status_code(error) != 409:
                raise BusinessException(
                    ErrorCode.STORAGE_UPLOAD_FAILED,
                    f"创建存储桶失败: {error}",
                ) from error

    async def upload(
        self,
        data: bytes,
        original_filename: str | None,
        content_type: str | None,
        prefix: str,
    ) -> str:
        key = self._keys.generate(original_filename, prefix)
        arguments: dict[str, Any] = {
            "Bucket": self._settings.storage_bucket,
            "Key": key,
            "Body": data,
            "ContentLength": len(data),
        }
        if content_type is not None:
            arguments["ContentType"] = content_type
        try:
            await self._call(self._client.put_object, **arguments)
        except (BotoCoreError, ClientError) as error:
            raise BusinessException(
                ErrorCode.STORAGE_UPLOAD_FAILED,
                f"文件存储失败: {error}",
            ) from error
        return key

    async def download(self, key: str) -> bytes:
        try:
            response = await self._call(
                self._client.get_object,
                Bucket=self._settings.storage_bucket,
                Key=key,
            )
            return await self._executor.run(response["Body"].read)
        except ClientError as error:
            if self._status_code(error) == 404:
                raise BusinessException(
                    ErrorCode.STORAGE_DOWNLOAD_FAILED,
                    f"文件不存在: {key}",
                ) from error
            raise BusinessException(
                ErrorCode.STORAGE_DOWNLOAD_FAILED,
                f"文件下载失败: {error}",
            ) from error
        except BotoCoreError as error:
            raise BusinessException(
                ErrorCode.STORAGE_DOWNLOAD_FAILED,
                f"文件下载失败: {error}",
            ) from error

    async def exists(self, key: str) -> bool:
        try:
            await self._call(
                self._client.head_object,
                Bucket=self._settings.storage_bucket,
                Key=key,
            )
            return True
        except ClientError as error:
            if self._status_code(error) == 404:
                return False
            raise BusinessException(
                ErrorCode.STORAGE_DOWNLOAD_FAILED,
                f"检查文件状态失败: {error}",
            ) from error
        except BotoCoreError as error:
            raise BusinessException(
                ErrorCode.STORAGE_DOWNLOAD_FAILED,
                f"检查文件状态失败: {error}",
            ) from error

    async def stat(self, key: str) -> StoredObject:
        try:
            response = await self._call(
                self._client.head_object,
                Bucket=self._settings.storage_bucket,
                Key=key,
            )
        except (BotoCoreError, ClientError) as error:
            raise BusinessException(
                ErrorCode.STORAGE_DOWNLOAD_FAILED,
                "获取文件信息失败",
            ) from error
        return StoredObject(
            key=key,
            content_type=response.get("ContentType"),
            content_length=int(response["ContentLength"]),
        )

    async def delete(self, key: str | None) -> None:
        if not key:
            return
        try:
            await self._call(
                self._client.delete_object,
                Bucket=self._settings.storage_bucket,
                Key=key,
            )
        except ClientError as error:
            if self._status_code(error) == 404:
                return
            raise BusinessException(
                ErrorCode.STORAGE_DELETE_FAILED,
                f"文件删除失败: {error}",
            ) from error
        except BotoCoreError as error:
            raise BusinessException(
                ErrorCode.STORAGE_DELETE_FAILED,
                f"文件删除失败: {error}",
            ) from error

    def object_url(self, key: str) -> str:
        endpoint = self._settings.storage_endpoint.rstrip("/")
        return f"{endpoint}/{self._settings.storage_bucket}/{key}"

    async def _call(self, function: Any, **arguments: Any) -> Any:
        return await asyncio.wait_for(
            self._executor.run(function, **arguments),
            timeout=self._settings.storage_api_call_timeout_seconds,
        )

    @staticmethod
    def _status_code(error: ClientError) -> int | None:
        metadata = cast(
            dict[str, Any],
            error.response.get("ResponseMetadata") or {},
        )
        status = metadata.get("HTTPStatusCode")
        return int(status) if status is not None else None
