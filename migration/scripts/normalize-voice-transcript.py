#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def normalize_message(message: dict[str, Any]) -> dict[str, Any]:
    document = message.get("json")
    if isinstance(document, dict):
        document = dict(document)
        document.pop("timestamp", None)
    return {"json": document}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    transcript = json.loads(args.input.read_text(encoding="utf-8"))
    normalized = {
        "closeCode": transcript.get("closeCode"),
        "closeReason": transcript.get("closeReason"),
        "received": [normalize_message(message) for message in transcript.get("received", [])],
        "sent": [normalize_message(message) for message in transcript.get("sent", [])],
    }
    args.output.write_text(
        json.dumps(
            normalized,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
