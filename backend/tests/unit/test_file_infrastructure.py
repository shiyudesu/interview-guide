from __future__ import annotations

import uuid
from datetime import datetime

import pytest

from interview_guide.common.api.models import utf16_code_unit_length
from interview_guide.common.errors import BusinessException
from interview_guide.infrastructure.file.content_type import ContentTypeDetector
from interview_guide.infrastructure.file.hash import sha256_bytes, sha256_chunks
from interview_guide.infrastructure.file.text import (
    clean_text,
    clean_text_with_limit,
    clean_to_single_line,
    strip_html,
)
from interview_guide.infrastructure.file.validation import (
    is_allowed_type,
    is_knowledge_base_mime_type,
    is_markdown_extension,
    validate_document_character_limit,
    validate_file,
)
from interview_guide.infrastructure.storage.keys import (
    FileKeyGenerator,
    convert_to_pinyin,
)


def test_file_hash_matches_streaming_hash() -> None:
    content = "固定文件内容".encode()

    assert sha256_bytes(content) == sha256_chunks([content[:4], content[4:]])


def test_resume_mime_list_preserves_bidirectional_substring_matching() -> None:
    assert is_allowed_type("application/pdf; charset=binary", ["application/pdf"])
    assert is_allowed_type("pdf", ["application/pdf"])
    assert not is_allowed_type(None, ["application/pdf"])


def test_markdown_and_rtf_knowledge_base_special_cases() -> None:
    assert is_markdown_extension("guide.MDOWN")
    assert is_knowledge_base_mime_type("application/rtf")


def test_file_size_and_utf16_limits_fail_whole_input() -> None:
    with pytest.raises(BusinessException, match="请选择要上传的简历文件"):
        validate_file(b"", 10, "简历")
    with pytest.raises(BusinessException, match="文件大小超过限制"):
        validate_file(b"12345", 4, "简历")

    oversized = "😀" * ((5 * 1024 * 1024) // 2 + 1)
    assert utf16_code_unit_length(oversized) > 5 * 1024 * 1024
    with pytest.raises(BusinessException, match="文档内容超过最大字符限制"):
        validate_document_character_limit(oversized)


def test_content_type_detection_falls_back_only_on_io_error() -> None:
    def failing_detector(data: bytes, filename: str | None) -> str:
        del data, filename
        raise OSError("read failed")

    detector = ContentTypeDetector(failing_detector)

    assert (
        detector.detect(
            b"content",
            "resume.pdf",
            "application/upload-fallback",
        )
        == "application/upload-fallback"
    )


def test_text_cleaning_matches_compatibility_rules() -> None:
    source = (
        "个人简历\r\n============\nimage001.png\n"
        "https://example.com/photo.jpg\nfile:///tmp/temp.html\n\n\n技能：Java   "
    )

    assert clean_text(source) == "个人简历\n\n技能：Java"
    assert clean_to_single_line("多个   空格\n之间") == "多个 空格 之间"
    assert strip_html("<p>A &amp; B&nbsp; C</p>") == "A & B C"
    assert clean_text_with_limit("这是一段比较长的文本内容", 10) == "这是一段比较长的文本"


def test_file_key_uses_date_uuid_pinyin_and_safe_characters() -> None:
    generator = FileKeyGenerator(
        now=lambda: datetime(2026, 8, 16, 8, 0),
        uuid_factory=lambda: uuid.UUID("12345678-0000-0000-0000-000000000000"),
    )

    assert convert_to_pinyin("测试 简历.pdf") == "CeShi_JianLi.pdf"
    assert generator.generate("测试 简历.pdf", "resumes") == (
        "resumes/2026/08/16/12345678_CeShi_JianLi.pdf"
    )
