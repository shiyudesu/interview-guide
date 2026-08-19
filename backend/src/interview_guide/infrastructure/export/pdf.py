from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from urllib.parse import quote_plus

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Flowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from interview_guide.common.errors import BusinessException, ErrorCode

HEADER_COLOR = colors.Color(41 / 255, 128 / 255, 185 / 255)
SECTION_COLOR = colors.Color(52 / 255, 73 / 255, 94 / 255)
SUCCESS_COLOR = colors.Color(39 / 255, 174 / 255, 96 / 255)
WARNING_COLOR = colors.Color(241 / 255, 196 / 255, 15 / 255)
ERROR_COLOR = colors.Color(231 / 255, 76 / 255, 60 / 255)


def sanitize_pdf_text(value: str | None) -> str:
    if value is None:
        return ""
    return "".join(
        character for character in value if unicodedata.category(character) not in {"So", "Cs"}
    ).strip()


def score_color(score: int) -> colors.Color:
    if score >= 80:
        return SUCCESS_COLOR
    if score >= 60:
        return WARNING_COLOR
    return ERROR_COLOR


def form_urlencode(value: str) -> str:
    return quote_plus(value, safe="")


def pdf_download_headers(filename: str) -> dict[str, str]:
    encoded = form_urlencode(filename)
    return {
        "Content-Disposition": f"attachment; filename*=UTF-8''{encoded}",
        "Content-Type": "application/pdf",
    }


def original_file_download_headers(
    filename: str,
    content_type: str | None,
) -> dict[str, str]:
    encoded = form_urlencode(filename).replace("+", "%20")
    return {
        "Content-Disposition": (f"attachment; filename=\"{encoded}\"; filename*=UTF-8''{encoded}"),
        "Content-Type": content_type or "application/octet-stream",
    }


@dataclass(frozen=True)
class ScoreRow:
    dimension: str
    score: int
    maximum: int


class PdfDocumentBuilder:
    def __init__(self, font_path: Path) -> None:
        if not font_path.is_file():
            raise BusinessException(
                ErrorCode.EXPORT_PDF_FAILED,
                "字体文件缺失，请联系管理员",
            )
        self._font_name = f"ZhuqueFangsong-{abs(hash(font_path.resolve()))}"
        if self._font_name not in pdfmetrics.getRegisteredFontNames():
            try:
                pdfmetrics.registerFont(TTFont(self._font_name, str(font_path)))
                pdfmetrics.registerFontFamily(
                    self._font_name,
                    normal=self._font_name,
                    bold=self._font_name,
                    italic=self._font_name,
                    boldItalic=self._font_name,
                )
            except Exception as error:
                raise BusinessException(
                    ErrorCode.EXPORT_PDF_FAILED,
                    f"创建字体失败: {error}",
                ) from error
        self._styles = getSampleStyleSheet()

    def build(
        self,
        title: str,
        sections: list[tuple[str, list[str]]],
        score_rows: list[ScoreRow] | None = None,
        score_after_sections: int = 0,
        page_break_after_titles: frozenset[str] = frozenset(),
    ) -> bytes:
        output = BytesIO()
        document = SimpleDocTemplate(
            output,
            pagesize=A4,
            leftMargin=36,
            rightMargin=36,
            topMargin=36,
            bottomMargin=36,
            title=sanitize_pdf_text(title),
        )
        title_style = ParagraphStyle(
            "report-title",
            parent=self._styles["Title"],
            fontName=self._font_name,
            fontSize=24,
            leading=30,
            alignment=1,
            textColor=HEADER_COLOR,
        )
        section_style = ParagraphStyle(
            "section-title",
            parent=self._styles["Heading2"],
            fontName=self._font_name,
            fontSize=14,
            leading=18,
            textColor=SECTION_COLOR,
            spaceBefore=10,
        )
        body_style = ParagraphStyle(
            "body",
            parent=self._styles["BodyText"],
            fontName=self._font_name,
            fontSize=10,
            leading=14,
        )
        story: list[Flowable] = [
            Paragraph(
                f"<b>{sanitize_pdf_text(title)}</b>",
                title_style,
            )
        ]
        if score_rows and score_after_sections == 0:
            self._append_scores(story, score_rows, section_style, body_style)
        for index, (section_title, paragraphs) in enumerate(sections, start=1):
            story.append(Spacer(1, 3 * mm))
            story.append(
                Paragraph(
                    f"<b>{sanitize_pdf_text(section_title)}</b>",
                    section_style,
                )
            )
            if section_title in page_break_after_titles:
                story.append(PageBreak())
            story.extend(
                Paragraph(sanitize_pdf_text(paragraph), body_style) for paragraph in paragraphs
            )
            if score_rows and index == score_after_sections:
                self._append_scores(story, score_rows, section_style, body_style)
        document.build(story)
        return output.getvalue()

    def _append_scores(
        self,
        story: list[Flowable],
        rows: list[ScoreRow],
        section_style: ParagraphStyle,
        body_style: ParagraphStyle,
    ) -> None:
        story.extend(
            [
                Spacer(1, 5 * mm),
                Paragraph("<b>各维度评分</b>", section_style),
                self._score_table(rows, body_style),
            ]
        )

    def _score_table(
        self,
        rows: list[ScoreRow],
        body_style: ParagraphStyle,
    ) -> Table:
        data = [
            [
                Paragraph(sanitize_pdf_text(row.dimension), body_style),
                Paragraph(
                    (
                        f'<font color="{score_color(row.score * 100 // row.maximum).hexval()}">'
                        f"{row.score} / {row.maximum}</font>"
                    ),
                    body_style,
                ),
            ]
            for row in rows
        ]
        table = Table(data, colWidths=[2 * 55 * mm, 55 * mm])
        table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
                ]
            )
        )
        return table
