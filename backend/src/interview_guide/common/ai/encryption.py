from __future__ import annotations

import base64
import fcntl
import hashlib
import os
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from interview_guide.common.config.settings import Settings
from interview_guide.common.errors import BusinessException, ErrorCode

NONCE_BYTES = 12
KEY_BYTES = 32


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
    return load_or_create_key(settings.ai_config_encryption_key_file)


def load_or_create_key(
    path: Path,
    key_factory: Callable[[int], bytes] = secrets.token_bytes,
) -> str:
    resolved = path.expanduser().resolve()
    try:
        resolved.parent.mkdir(parents=True, exist_ok=True)
        lock_path = resolved.with_name(f".{resolved.name}.lock")
        with lock_path.open("a+b") as lock:
            os.chmod(lock_path, 0o600)
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            if not resolved.exists():
                raw_key = key_factory(KEY_BYTES)
                if len(raw_key) != KEY_BYTES:
                    raise ValueError(f"key must contain {KEY_BYTES} bytes")
                temporary = resolved.with_name(f".{resolved.name}.{os.getpid()}.tmp")
                try:
                    with temporary.open("xb") as target:
                        os.chmod(temporary, 0o600)
                        target.write(base64.b64encode(raw_key) + b"\n")
                        target.flush()
                        os.fsync(target.fileno())
                    os.replace(temporary, resolved)
                finally:
                    temporary.unlink(missing_ok=True)
            configured = resolved.read_text(encoding="ascii").strip()
            decoded = base64.b64decode(configured, validate=True)
            if len(decoded) != KEY_BYTES:
                raise ValueError(f"key must decode to {KEY_BYTES} bytes")
            os.chmod(resolved, 0o600)
            return configured
    except (OSError, UnicodeError, ValueError) as error:
        raise BusinessException(
            ErrorCode.PROVIDER_CONFIG_READ_FAILED,
            f"无法读取或创建 Provider 加密密钥文件: {resolved}",
        ) from error


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

    def encrypt(self, plaintext: str, *, aad: bytes | None = None) -> EncryptedValue:
        try:
            nonce = self._nonce_factory(NONCE_BYTES)
            if len(nonce) != NONCE_BYTES:
                raise ValueError(f"nonce must contain {NONCE_BYTES} bytes")
            ciphertext = AESGCM(self._key).encrypt(
                nonce,
                plaintext.encode(),
                aad,
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

    def decrypt(
        self,
        nonce_base64: str,
        ciphertext_base64: str,
        *,
        aad: bytes | None = None,
    ) -> str:
        try:
            nonce = base64.b64decode(nonce_base64, validate=True)
            ciphertext = base64.b64decode(ciphertext_base64, validate=True)
            plaintext = AESGCM(self._key).decrypt(nonce, ciphertext, aad)
            return plaintext.decode()
        except Exception as error:
            raise BusinessException(
                ErrorCode.PROVIDER_CONFIG_READ_FAILED,
                "解密 Provider API Key 失败，请检查加密主密钥或 provider_key 卷",
            ) from error
