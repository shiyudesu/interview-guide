from __future__ import annotations

import logging
from collections.abc import Callable

import magic

logger = logging.getLogger(__name__)

Detector = Callable[[bytes, str | None], str]


def libmagic_detector(data: bytes, filename: str | None) -> str:
    del filename
    return str(magic.from_buffer(data, mime=True))


class ContentTypeDetector:
    def __init__(self, detector: Detector = libmagic_detector) -> None:
        self._detector = detector

    def detect(
        self,
        data: bytes,
        filename: str | None,
        fallback_content_type: str | None = None,
    ) -> str | None:
        try:
            return self._detector(data, filename)
        except (OSError, magic.MagicException) as error:
            logger.warning(
                "unable to detect file type; using upload Content-Type error=%s",
                error,
            )
            return fallback_content_type

    @staticmethod
    def is_pdf(content_type: str | None) -> bool:
        return content_type is not None and "pdf" in content_type.lower()

    @staticmethod
    def is_word_document(content_type: str | None) -> bool:
        if content_type is None:
            return False
        normalized = content_type.lower()
        return "msword" in normalized or "wordprocessingml" in normalized

    @staticmethod
    def is_plain_text(content_type: str | None) -> bool:
        return content_type is not None and content_type.lower().startswith("text/")

    @staticmethod
    def is_markdown(content_type: str | None, filename: str | None) -> bool:
        if content_type is not None:
            normalized = content_type.lower()
            if "markdown" in normalized or "x-markdown" in normalized:
                return True
        if filename is None:
            return False
        return filename.lower().endswith((".md", ".markdown", ".mdown"))
