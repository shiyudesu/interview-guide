from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def complete_jsonl_lines(path: Path) -> list[str]:
    if not path.is_file():
        return []
    document = path.read_text(encoding="utf-8")
    lines = document.splitlines()
    if lines and not document.endswith("\n"):
        try:
            json.loads(lines[-1])
        except json.JSONDecodeError:
            lines.pop()
    return [line for line in lines if line]


def read_jsonl_records(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in complete_jsonl_lines(path)]
