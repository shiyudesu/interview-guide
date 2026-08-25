from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from urllib.parse import quote

from interview_guide.common.config.settings import Settings
from interview_guide.common.errors import BusinessException, ErrorCode
from interview_guide.common.runtime import BlockingExecutor

logger = logging.getLogger(__name__)


class AuthMailer:
    def __init__(self, settings: Settings, executor: BlockingExecutor) -> None:
        self._settings = settings
        self._executor = executor

    async def send_email_verification(
        self,
        email: str,
        display_name: str | None,
        token: str,
    ) -> None:
        url = self._action_url("verify-email", token)
        await self._send(
            email,
            "验证你的 AI Interview 账号",
            (
                f"{display_name or '你好'}：\n\n"
                f"请在 24 小时内打开以下链接完成邮箱验证：\n{url}\n\n"
                "如果不是你发起的注册，请忽略此邮件。"
            ),
        )

    async def send_password_reset(
        self,
        email: str,
        display_name: str | None,
        token: str,
    ) -> None:
        url = self._action_url("reset-password", token)
        await self._send(
            email,
            "重置你的 AI Interview 密码",
            (
                f"{display_name or '你好'}：\n\n"
                f"请在 1 小时内打开以下链接重置密码：\n{url}\n\n"
                "如果不是你发起的操作，请忽略此邮件。"
            ),
        )

    def _action_url(self, path: str, token: str) -> str:
        return f"{self._settings.auth_public_url.rstrip('/')}/{path}?token={quote(token)}"

    async def _send(self, recipient: str, subject: str, body: str) -> None:
        try:
            await self._executor.run(self._send_blocking, recipient, subject, body)
        except (OSError, smtplib.SMTPException) as error:
            logger.exception("authentication email delivery failed")
            raise BusinessException(ErrorCode.AUTH_EMAIL_DELIVERY_FAILED) from error

    def _send_blocking(self, recipient: str, subject: str, body: str) -> None:
        message = EmailMessage()
        message["From"] = self._settings.auth_smtp_from_email
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(body)
        password = self._settings.auth_smtp_password.get_secret_value()
        smtp_class = smtplib.SMTP_SSL if self._settings.auth_smtp_ssl else smtplib.SMTP
        with smtp_class(
            self._settings.auth_smtp_host,
            self._settings.auth_smtp_port,
            timeout=self._settings.auth_smtp_timeout_seconds,
        ) as connection:
            if self._settings.auth_smtp_starttls:
                connection.starttls()
            if self._settings.auth_smtp_username:
                connection.login(self._settings.auth_smtp_username, password)
            connection.send_message(message)
