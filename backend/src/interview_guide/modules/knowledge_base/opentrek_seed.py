from __future__ import annotations

import argparse
import asyncio
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from interview_guide.common.ai.user_providers import UserProviderRepository
from interview_guide.common.config.settings import Settings, get_settings
from interview_guide.common.db.models import KnowledgeBase
from interview_guide.common.db.session import Database
from interview_guide.common.runtime import BlockingExecutor
from interview_guide.infrastructure.file.content_type import ContentTypeDetector
from interview_guide.infrastructure.file.hash import sha256_bytes
from interview_guide.infrastructure.storage.s3 import S3Storage
from interview_guide.modules.auth.models import normalized_email
from interview_guide.modules.auth.repository import AuthRepository
from interview_guide.modules.knowledge_base.repository import KnowledgeBaseRepository

MAPPING_ENV_NAME = "APP_OPENTREK_KB_MAPPINGS_JSON"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="为用户创建只读 OpenTrek Kortex 知识库影子记录",
    )
    parser.add_argument("--user-email", required=True)
    parser.add_argument("--file", required=True, type=Path)
    parser.add_argument("--kb-code", required=True)
    parser.add_argument("--name")
    parser.add_argument("--category")
    parser.add_argument("--env-file", type=Path, default=Path(".env.campus"))
    parser.add_argument("--replace-mapping", action="store_true")
    parser.add_argument("--skip-env-update", action="store_true")
    arguments = parser.parse_args()
    asyncio.run(
        seed_opentrek_knowledge_base(
            settings=get_settings(),
            user_email=normalized_email(arguments.user_email),
            source_file=arguments.file,
            kb_code=arguments.kb_code,
            name=arguments.name,
            category=arguments.category,
            env_file=arguments.env_file,
            replace_mapping=arguments.replace_mapping,
            update_mapping=not arguments.skip_env_update,
        )
    )


async def seed_opentrek_knowledge_base(
    *,
    settings: Settings,
    user_email: str,
    source_file: Path,
    kb_code: str,
    name: str | None,
    category: str | None,
    env_file: Path,
    replace_mapping: bool,
    update_mapping: bool = True,
) -> None:
    resolved_kb_code = kb_code.strip()
    if not resolved_kb_code:
        raise SystemExit("kbCode 不能为空。")
    if not source_file.is_file():
        raise SystemExit(f"预置知识库文件不存在: {source_file}")
    database = Database(settings)
    executor = BlockingExecutor(settings.blocking_worker_count)
    storage = S3Storage(settings, executor)
    try:
        user = await AuthRepository(database.sessions, settings).get_user_by_email(user_email)
        if user is None or user.kind != "HUMAN" or user.status != "ACTIVE":
            raise SystemExit(f"已激活普通账号不存在: {user_email}")
        data = await executor.run(source_file.read_bytes)
        file_hash = sha256_bytes(data)
        detected_type = ContentTypeDetector().detect(data, source_file.name, None)
        defaults = await UserProviderRepository(database.sessions, user.id).default_aliases()
        await storage.start()
        async with database.sessions() as session:
            repository = KnowledgeBaseRepository(session, user.id)
            existing = await repository.get_by_hash(file_hash)
            if existing is None:
                await session.rollback()
                storage_key = await storage.upload(
                    data,
                    source_file.name,
                    detected_type,
                    f"users/{user.id}/knowledgebases",
                )
                timestamp = datetime.now()
                try:
                    async with session.begin():
                        entity = await repository.add(
                            KnowledgeBase(
                                access_count=1,
                                category=normalized_optional(category),
                                chunk_count=0,
                                content_type=detected_type,
                                embedding_provider_alias=defaults.default_embedding_provider_id,
                                file_hash=file_hash,
                                file_size=len(data),
                                last_accessed_at=timestamp,
                                name=normalized_optional(name) or source_file.stem or "预置知识库",
                                original_filename=source_file.name,
                                question_count=0,
                                question_provider_alias=defaults.default_chat_provider_id,
                                storage_key=storage_key,
                                storage_url=storage.object_url(storage_key),
                                uploaded_at=timestamp,
                                vector_error=None,
                                vector_status="COMPLETED",
                                user_id=user.id,
                            )
                        )
                except BaseException:
                    await storage.delete(storage_key)
                    raise
            else:
                entity = existing
        if update_mapping:
            update_mapping_env_file(
                env_file,
                file_hash,
                resolved_kb_code,
                replace=replace_mapping,
            )
        print(
            json.dumps(
                {
                    "knowledgeBaseId": entity.id,
                    "userId": str(user.id),
                    "fileHash": file_hash,
                    "kbCode": resolved_kb_code,
                    "envFile": str(env_file) if update_mapping else None,
                },
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )
    finally:
        await database.close()
        await executor.shutdown()


def update_mapping_env_file(
    path: Path,
    file_hash: str,
    kb_code: str,
    *,
    replace: bool = False,
) -> None:
    if not path.is_file():
        raise SystemExit(f"环境文件不存在，拒绝自动创建或覆盖: {path}")
    original = path.read_text(encoding="utf-8")
    lines = original.splitlines(keepends=True)
    current: Any = []
    found_index: int | None = None
    for index, line in enumerate(lines):
        if line.lstrip().startswith(f"{MAPPING_ENV_NAME}="):
            found_index = index
            raw = line.split("=", 1)[1].strip()
            if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in {"'", '"'}:
                raw = raw[1:-1]
            try:
                current = json.loads(raw or "[]")
            except ValueError as error:
                raise SystemExit(f"{MAPPING_ENV_NAME} 不是合法 JSON") from error
            break
    mappings = normalize_mapping_document(current)
    existing = mappings.get(file_hash)
    if existing is not None and existing != kb_code and not replace:
        raise SystemExit(
            f"文件 {file_hash} 已映射到 {existing}；如需替换请增加 --replace-mapping。"
        )
    mappings[file_hash] = kb_code
    rendered = json.dumps(
        [{"fileHash": key, "kbCode": value} for key, value in sorted(mappings.items())],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    new_line = f"{MAPPING_ENV_NAME}='{rendered}'\n"
    if found_index is None:
        if lines and not lines[-1].endswith(("\n", "\r")):
            lines[-1] += "\n"
        lines.append(new_line)
    else:
        line_ending = "\r\n" if lines[found_index].endswith("\r\n") else "\n"
        lines[found_index] = new_line.rstrip("\n") + line_ending
    atomic_write(path, "".join(lines))


def normalize_mapping_document(value: Any) -> dict[str, str]:
    if isinstance(value, dict):
        items = list(value.items())
    elif isinstance(value, list):
        items = [
            (item.get("fileHash"), item.get("kbCode")) for item in value if isinstance(item, dict)
        ]
    else:
        raise SystemExit(f"{MAPPING_ENV_NAME} 必须是数组或对象")
    result: dict[str, str] = {}
    for raw_hash, raw_code in items:
        file_hash = str(raw_hash or "").strip().lower()
        kb_code = str(raw_code or "").strip()
        if len(file_hash) != 64 or any(
            character not in "0123456789abcdef" for character in file_hash
        ):
            raise SystemExit(f"{MAPPING_ENV_NAME} 包含无效 SHA-256")
        if not kb_code:
            raise SystemExit(f"{MAPPING_ENV_NAME} 包含空 kbCode")
        result[file_hash] = kb_code
    return result


def atomic_write(path: Path, content: str) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_path, path.stat().st_mode)
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def normalized_optional(value: str | None) -> str | None:
    normalized = value.strip() if value is not None else ""
    return normalized or None
