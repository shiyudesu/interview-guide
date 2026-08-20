from __future__ import annotations

import re

IMAGE_FILENAME_LINE = re.compile(r"^image\d+\.(png|jpe?g|gif|bmp|webp)\s*$", re.MULTILINE)
IMAGE_URL = re.compile(
    r"https?://\S+?\.(png|jpe?g|gif|bmp|webp)(\?\S*)?",
    re.IGNORECASE,
)
FILE_URL = re.compile(r"file:(//)?\S+", re.IGNORECASE)
SEPARATOR_LINE = re.compile(r"^\s*[-_*=]{3,}\s*$", re.MULTILINE)
CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
HTML_TAGS = re.compile(r"<[^>]+>")
TRAILING_WHITESPACE = re.compile(r"[ \t]+$", re.MULTILINE)
EXCESS_NEWLINES = re.compile(r"\n{3,}")
LINE_BREAKS = re.compile(r"[\r\n]+")
ASCII_WHITESPACE = re.compile(r"\s+", re.ASCII)


def clean_text(text: str | None) -> str:
    if text is None or not text.strip():
        return ""
    cleaned = CONTROL_CHARS.sub("", text)
    cleaned = IMAGE_FILENAME_LINE.sub("", cleaned)
    cleaned = IMAGE_URL.sub("", cleaned)
    cleaned = FILE_URL.sub("", cleaned)
    cleaned = SEPARATOR_LINE.sub("", cleaned)
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = TRAILING_WHITESPACE.sub("", cleaned)
    cleaned = EXCESS_NEWLINES.sub("\n\n", cleaned)
    return cleaned.strip()


def truncate_characters(text: str, max_length: int) -> str:
    return text[:max_length]


def clean_text_with_limit(text: str | None, max_length: int) -> str:
    return truncate_characters(clean_text(text), max_length)


def clean_to_single_line(text: str | None) -> str:
    if text is None or not text.strip():
        return ""
    return ASCII_WHITESPACE.sub(" ", LINE_BREAKS.sub(" ", text)).strip()


def strip_html(text: str | None) -> str:
    if text is None or not text.strip():
        return ""
    cleaned = HTML_TAGS.sub(" ", text)
    for entity, value in (
        ("&nbsp;", " "),
        ("&amp;", "&"),
        ("&lt;", "<"),
        ("&gt;", ">"),
        ("&quot;", '"'),
        ("&apos;", "'"),
    ):
        cleaned = cleaned.replace(entity, value)
    return ASCII_WHITESPACE.sub(" ", cleaned).strip()
