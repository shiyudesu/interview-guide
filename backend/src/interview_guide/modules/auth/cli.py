from __future__ import annotations

import argparse
import asyncio
import getpass
import json

from interview_guide.common.config.settings import get_settings
from interview_guide.common.db.session import Database
from interview_guide.common.runtime import BlockingExecutor
from interview_guide.modules.auth.models import normalized_email, validate_password_length
from interview_guide.modules.auth.passwords import PasswordService
from interview_guide.modules.auth.repository import AuthRepository
from interview_guide.modules.auth.service import utc_now


def create_admin_main() -> None:
    parser = argparse.ArgumentParser(description="创建 InterviewGuide 管理员")
    parser.add_argument("--email", required=True)
    parser.add_argument("--display-name")
    arguments = parser.parse_args()
    password = getpass.getpass("管理员密码: ")
    confirmation = getpass.getpass("再次输入管理员密码: ")
    if password != confirmation:
        raise SystemExit("两次输入的密码不一致。")
    validate_password_length(password)
    asyncio.run(
        create_admin(
            normalized_email(arguments.email),
            arguments.display_name,
            password,
        )
    )


def create_user_main() -> None:
    parser = argparse.ArgumentParser(description="创建已验证的 InterviewGuide 普通用户")
    parser.add_argument("--email", required=True)
    parser.add_argument("--display-name")
    arguments = parser.parse_args()
    password = getpass.getpass("用户密码: ")
    confirmation = getpass.getpass("再次输入用户密码: ")
    if password != confirmation:
        raise SystemExit("两次输入的密码不一致。")
    validate_password_length(password)
    asyncio.run(
        create_user(
            normalized_email(arguments.email),
            arguments.display_name,
            password,
        )
    )


async def create_admin(email: str, display_name: str | None, password: str) -> None:
    settings = get_settings()
    database = Database(settings)
    executor = BlockingExecutor(settings.blocking_worker_count)
    try:
        repository = AuthRepository(database.sessions, settings)
        existing = await repository.get_user_by_email(email)
        if existing is not None:
            raise SystemExit(f"用户已存在: {email}")
        password_hash = await PasswordService(executor).hash(password)
        user = await repository.create_human_user(
            email=email,
            display_name=display_name,
            password_hash=password_hash,
            role="ADMIN",
            status="ACTIVE",
            now=utc_now(),
            email_verified=True,
        )
        print(f"管理员已创建: {user.email} ({user.id})")
    finally:
        await database.close()
        await executor.shutdown()


async def create_user(email: str, display_name: str | None, password: str) -> None:
    settings = get_settings()
    database = Database(settings)
    executor = BlockingExecutor(settings.blocking_worker_count)
    try:
        repository = AuthRepository(database.sessions, settings)
        existing = await repository.get_user_by_email(email)
        if existing is not None:
            raise SystemExit(f"用户已存在: {email}")
        password_hash = await PasswordService(executor).hash(password)
        user = await repository.create_human_user(
            email=email,
            display_name=display_name,
            password_hash=password_hash,
            role="USER",
            status="ACTIVE",
            now=utc_now(),
            email_verified=True,
        )
        print(f"普通用户已创建: {user.email} ({user.id})")
    finally:
        await database.close()
        await executor.shutdown()


def claim_legacy_data_main() -> None:
    parser = argparse.ArgumentParser(description="将 legacy-owner 数据转移给管理员")
    parser.add_argument("--admin-email", required=True)
    parser.add_argument("--yes", action="store_true")
    arguments = parser.parse_args()
    if not arguments.yes:
        raise SystemExit("该命令会转移全部存量资源；确认后请增加 --yes。")
    asyncio.run(claim_legacy_data(normalized_email(arguments.admin_email)))


async def claim_legacy_data(email: str) -> None:
    settings = get_settings()
    database = Database(settings)
    try:
        repository = AuthRepository(database.sessions, settings)
        user = await repository.get_user_by_email(email)
        if user is None or user.kind != "HUMAN" or user.role != "ADMIN":
            raise SystemExit(f"管理员不存在: {email}")
        counts = await repository.claim_legacy_resources(user.id)
        print(json.dumps(counts, ensure_ascii=False, sort_keys=True))
    finally:
        await database.close()
