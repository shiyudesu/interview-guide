from __future__ import annotations

from datetime import datetime
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pdfminer.high_level import extract_text
from pypdf import PdfReader

from interview_guide.common.errors import BusinessException
from interview_guide.infrastructure.export.pdf import (
    PdfDocumentBuilder,
    ScoreRow,
    original_file_download_headers,
    pdf_download_headers,
    sanitize_pdf_text,
)
from interview_guide.modules.resume.service import ResumeService

BACKEND_ROOT = Path(__file__).resolve().parents[2]
FONT_PATH = BACKEND_ROOT / "resources/fonts/ZhuqueFangsong-Regular.ttf"


def test_pdf_visible_text_page_count_and_emoji_sanitization() -> None:
    builder = PdfDocumentBuilder(FONT_PATH)

    pdf = builder.build(
        "简历分析报告",
        [
            ("基本信息", ["文件名: 测试简历.pdf"]),
            ("优势亮点", ["稳定可靠 😀"]),
        ],
        score_rows=[ScoreRow("项目经验", 32, 40)],
    )

    reader = PdfReader(BytesIO(pdf))
    text = extract_text(BytesIO(pdf))
    assert len(reader.pages) == 1
    assert "简历分析报告" in text
    assert "基本信息" in text
    assert "稳定可靠" in text
    assert "😀" not in text


def test_missing_font_fails_explicitly(tmp_path: Path) -> None:
    with pytest.raises(BusinessException, match="字体文件缺失"):
        PdfDocumentBuilder(tmp_path / "missing.ttf")


def test_download_headers_encode_unicode_filenames() -> None:
    assert pdf_download_headers("模拟面试报告 session.pdf") == {
        "Content-Disposition": (
            "attachment; filename*=UTF-8''"
            "%E6%A8%A1%E6%8B%9F%E9%9D%A2%E8%AF%95%E6%8A%A5%E5%91%8A+session.pdf"
        ),
        "Content-Type": "application/pdf",
    }
    assert original_file_download_headers(
        "知识 库.md",
        "text/markdown",
    ) == {
        "Content-Disposition": (
            'attachment; filename="%E7%9F%A5%E8%AF%86%20%E5%BA%93.md"; '
            "filename*=UTF-8''%E7%9F%A5%E8%AF%86%20%E5%BA%93.md"
        ),
        "Content-Type": "text/markdown",
    }


def test_sanitize_pdf_text_removes_unicode_symbol_and_surrogate() -> None:
    assert sanitize_pdf_text("A😀B\ud800C") == "ABC"


@pytest.mark.asyncio
async def test_resume_pdf_build_runs_through_the_bounded_executor() -> None:
    class RecordingExecutor:
        def __init__(self) -> None:
            self.calls: list[tuple[object, tuple[object, ...], dict[str, object]]] = []

        async def run(
            self,
            function: object,
            *args: object,
            **kwargs: object,
        ) -> bytes:
            self.calls.append((function, args, kwargs))
            return b"%PDF-test"

    executor = RecordingExecutor()
    service = ResumeService.__new__(ResumeService)
    service._blocking_executor = executor  # type: ignore[assignment]
    service._required = AsyncMock(  # type: ignore[method-assign]
        return_value=SimpleNamespace(
            original_filename="candidate.pdf",
            uploaded_at=datetime(2026, 8, 20, 8, 0),
        )
    )
    service._repository = SimpleNamespace(
        latest_analysis=AsyncMock(
            return_value=SimpleNamespace(
                content_score=12,
                expression_score=8,
                overall_score=80,
                project_score=32,
                skill_match_score=16,
                strengths_json="[]",
                structure_score=12,
                suggestions_json="[]",
                summary="稳定",
            )
        )
    )

    pdf, headers = await service.export_pdf(1)

    assert pdf == b"%PDF-test"
    assert headers["Content-Type"] == "application/pdf"
    assert len(executor.calls) == 1
    assert getattr(executor.calls[0][0], "__name__", "") == "build"
