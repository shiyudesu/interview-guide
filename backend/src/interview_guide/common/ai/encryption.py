from __future__ import annotations

import base64
import hashlib
import secrets
from collections.abc import Callable
from dataclasses import dataclass

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from interview_guide.common.config.settings import Settings
from interview_guide.common.errors import BusinessException, ErrorCode

DEV_FALLBACK_KEY = "interview-guide-dev-only-provider-api-key-encryption"
NONCE_BYTES = 12


@dataclass(frozen=True)
class EncryptedValue:
    nonce: str
    ciphertext: str


def resolve_key_bytes(configured_key: str) -> bytes:
    trimmed = configured_key.strip()
    try:
        decoded = base64.b64decode(trimmed, validate=True)
    except ValueError:
        decoded = b""
    if len(decoded) == 32:
        return decoded
    return hashlib.sha256(trimmed.encode()).digest()


def resolve_configured_key(settings: Settings) -> str:
    if settings.ai_config_encryption_key is not None:
        configured = settings.ai_config_encryption_key.get_secret_value()
        if configured.strip():
            return configured
    if settings.ai_config_require_encryption_key:
        raise BusinessException(
            ErrorCode.PROVIDER_CONFIG_READ_FAILED,
            "APP_AI_CONFIG_ENCRYPTION_KEY 未配置，无法初始化 Provider API Key 加密",
        )
    if not settings.ai_config_allow_fallback_encryption_key:
        raise BusinessException(
            ErrorCode.PROVIDER_CONFIG_READ_FAILED,
            "APP_AI_CONFIG_ENCRYPTION_KEY 未配置，且未显式允许 Provider API Key 开发 fallback",
        )
    return DEV_FALLBACK_KEY


class ApiKeyEncryption:
    def __init__(
        self,
        configured_key: str,
        nonce_factory: Callable[[int], bytes] = secrets.token_bytes,
    ) -> None:
        self._key = resolve_key_bytes(configured_key)
        self._nonce_factory = nonce_factory

    @classmethod
    def from_settings(cls, settings: Settings) -> ApiKeyEncryption:
        return cls(resolve_configured_key(settings))

    def encrypt(self, plaintext: str) -> EncryptedValue:
        try:
            nonce = self._nonce_factory(NONCE_BYTES)
            if len(nonce) != NONCE_BYTES:
                raise ValueError(f"nonce must contain {NONCE_BYTES} bytes")
            ciphertext = AESGCM(self._key).encrypt(
                nonce,
                plaintext.encode(),
                None,
            )
            return EncryptedValue(
                nonce=base64.b64encode(nonce).decode(),
                ciphertext=base64.b64encode(ciphertext).decode(),
            )
        except Exception as error:
            raise BusinessException(
                ErrorCode.PROVIDER_CONFIG_WRITE_FAILED,
                "加密 Provider API Key 失败",
            ) from error

    def decrypt(self, nonce_base64: str, ciphertext_base64: str) -> str:
        try:
            nonce = base64.b64decode(nonce_base64, validate=True)
            ciphertext = base64.b64decode(ciphertext_base64, validate=True)
            plaintext = AESGCM(self._key).decrypt(nonce, ciphertext, None)
            return plaintext.decode()
        except Exception as error:
            raise BusinessException(
                ErrorCode.PROVIDER_CONFIG_READ_FAILED,
                "解密 Provider API Key 失败，请检查 APP_AI_CONFIG_ENCRYPTION_KEY",
            ) from error
