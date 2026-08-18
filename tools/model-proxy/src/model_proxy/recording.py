from __future__ import annotations

import asyncio
import gzip
import hashlib
import json
import zlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SECRET_KEYS = {
    "api-key",
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "proxy-authorization",
    "set-cookie",
    "token",
    "x-api-key",
}
BINARY_KEYS = {
    "audio",
    "audio_data",
    "audioData",
    "bytes",
    "input_audio",
}


def redacted(value: str | bytes) -> str:
    raw = value.encode("utf-8") if isinstance(value, str) else value
    return f"<redacted:sha256:{hashlib.sha256(raw).hexdigest()[:16]}>"


def sanitize_headers(headers: Any) -> dict[str, list[str]]:
    sanitized: dict[str, list[str]] = {}
    for key in headers:
        values = headers.getall(key)
        if key.lower() in SECRET_KEYS:
            sanitized[key.lower()] = [redacted(value) for value in values]
        else:
            sanitized[key.lower()] = list(values)
    return dict(sorted(sanitized.items()))


def sanitize_json(value: Any, key: str | None = None) -> Any:
    if key is not None and key.lower() in SECRET_KEYS:
        return redacted(json.dumps(value, ensure_ascii=False, sort_keys=True))
    if isinstance(value, dict):
        return {
            item_key: sanitize_json(item_value, item_key) for item_key, item_value in value.items()
        }
    if isinstance(value, list):
        return [sanitize_json(item) for item in value]
    if key in BINARY_KEYS and isinstance(value, str) and len(value) >= 256:
        return {
            "encodedCharacters": len(value),
            "sha256": hashlib.sha256(value.encode("utf-8")).hexdigest(),
            "value": "<redacted-binary>",
        }
    return value


def body_record(
    body: bytes,
    content_type: str | None,
    max_record_bytes: int,
    content_encoding: str | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "bytes": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
    }
    decoded = body
    normalized_encoding = (content_encoding or "").lower().strip()
    try:
        if normalized_encoding == "gzip":
            decoded = gzip.decompress(body)
        elif normalized_encoding == "deflate":
            decoded = zlib.decompress(body)
    except (gzip.BadGzipFile, EOFError, zlib.error) as error:
        record["decodeError"] = type(error).__name__
        decoded = body
    if normalized_encoding:
        record["contentEncoding"] = normalized_encoding
        record["decodedBytes"] = len(decoded)
    sample = decoded[:max_record_bytes]
    record["truncated"] = len(sample) != len(decoded)
    normalized_content_type = (content_type or "").lower()
    if "json" in normalized_content_type:
        try:
            parsed = json.loads(sample.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            record["text"] = sample.decode("utf-8", errors="replace")
        else:
            record["json"] = sanitize_json(parsed)
    elif normalized_content_type.startswith("text/"):
        record["text"] = sample.decode("utf-8", errors="replace")
    return record


def websocket_message_record(data: Any, message_type: str) -> dict[str, Any]:
    if isinstance(data, str):
        raw = data.encode("utf-8")
        record: dict[str, Any] = {
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "type": message_type,
        }
        try:
            record["json"] = sanitize_json(json.loads(data))
        except json.JSONDecodeError:
            record["text"] = data
        return record
    raw = bytes(data)
    return {
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "type": message_type,
    }


class JsonlRecorder:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = asyncio.Lock()

    async def write(self, event: dict[str, Any]) -> None:
        document = {
            "recordedAt": datetime.now(UTC).isoformat(),
            **event,
        }
        line = json.dumps(document, ensure_ascii=False, sort_keys=True) + "\n"
        async with self._lock:
            await asyncio.to_thread(self._append, line)

    def _append(self, line: str) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as target:
            target.write(line)
