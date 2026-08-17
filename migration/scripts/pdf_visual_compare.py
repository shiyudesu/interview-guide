#!/usr/bin/env python3
"""Render Java/Python PDF pages and save pixel-difference evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import fitz
from PIL import Image, ImageChops, ImageStat


def render(pdf_path: Path, output_dir: Path, dpi: int) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    scale = dpi / 72
    paths: list[Path] = []
    with fitz.open(pdf_path) as document:
        for index, page in enumerate(document):
            pixmap = page.get_pixmap(
                matrix=fitz.Matrix(scale, scale),
                alpha=False,
            )
            output = output_dir / f"page-{index + 1}.png"
            pixmap.save(output)
            paths.append(output)
    return paths


def page_difference(left: Path, right: Path, output: Path) -> dict[str, object]:
    left_image = Image.open(left).convert("RGB")
    right_image = Image.open(right).convert("RGB")
    same_size = left_image.size == right_image.size
    width = max(left_image.width, right_image.width)
    height = max(left_image.height, right_image.height)
    left_canvas = Image.new("RGB", (width, height), "white")
    right_canvas = Image.new("RGB", (width, height), "white")
    left_canvas.paste(left_image, (0, 0))
    right_canvas.paste(right_image, (0, 0))
    difference = ImageChops.difference(left_canvas, right_canvas)
    output.parent.mkdir(parents=True, exist_ok=True)
    difference.save(output)
    mean = ImageStat.Stat(difference).mean
    return {
        "differenceImage": str(output),
        "leftSize": left_image.size,
        "meanAbsoluteChannelDifference": mean,
        "rightSize": right_image.size,
        "sameSize": same_size,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dpi", type=int, default=144)
    parser.add_argument("--java", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    args = parser.parse_args()

    java_pages = render(args.java, args.output / "java", args.dpi)
    python_pages = render(args.python, args.output / "python", args.dpi)
    pages = [
        page_difference(
            java_page,
            python_page,
            args.output / "difference" / f"page-{index + 1}.png",
        )
        for index, (java_page, python_page) in enumerate(
            zip(java_pages, python_pages)
        )
    ]
    report = {
        "dpi": args.dpi,
        "javaPageCount": len(java_pages),
        "pageCountEqual": len(java_pages) == len(python_pages),
        "pages": pages,
        "pythonPageCount": len(python_pages),
    }
    (args.output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
