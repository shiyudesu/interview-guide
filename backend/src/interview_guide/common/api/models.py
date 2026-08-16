from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


def to_camel(value: str) -> str:
    parts = value.split("_")
    return parts[0] + "".join(part[:1].upper() + part[1:] for part in parts[1:])


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        extra="ignore",
        populate_by_name=True,
        serialize_by_alias=True,
    )


def format_java_datetime(value: datetime, *, seconds_only: bool = False) -> str:
    if seconds_only or value.microsecond == 0:
        return value.isoformat(timespec="seconds")
    return value.isoformat(timespec="microseconds")


def java_utf16_length(value: str) -> int:
    return len(value.encode("utf-16-le")) // 2


def compact_json_text(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def normalize_request_id(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    normalized = value.strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,64}", normalized):
        raise ValueError("requestId格式不正确")
    return normalized
