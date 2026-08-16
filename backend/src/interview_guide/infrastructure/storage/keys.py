from __future__ import annotations

import re
import uuid
from collections.abc import Callable
from datetime import datetime

from pypinyin import Style, pinyin

SAFE_CHARACTER = re.compile(r"[A-Za-z0-9._-]")


def sanitize_character(character: str) -> str:
    return character if SAFE_CHARACTER.fullmatch(character) else "_"


def convert_to_pinyin(value: str) -> str:
    result: list[str] = []
    for character in value:
        syllables = pinyin(
            character,
            style=Style.NORMAL,
            heteronym=False,
            errors=lambda item: item,
        )
        syllable = syllables[0][0] if syllables else character
        if syllable != character and syllable:
            result.append(syllable[:1].upper() + syllable[1:])
        else:
            result.append(sanitize_character(character))
    return "".join(result)


class FileKeyGenerator:
    def __init__(
        self,
        now: Callable[[], datetime] = datetime.now,
        uuid_factory: Callable[[], uuid.UUID] = uuid.uuid4,
    ) -> None:
        self._now = now
        self._uuid_factory = uuid_factory

    def generate(self, original_filename: str | None, prefix: str) -> str:
        filename = original_filename or "unknown"
        safe_name = convert_to_pinyin(filename)
        date_path = self._now().strftime("%Y/%m/%d")
        identifier = str(self._uuid_factory())[:8]
        return f"{prefix}/{date_path}/{identifier}_{safe_name}"
