#!/usr/bin/env python3
"""Capture and compare SSE, WebSocket, files, and visible PDF evidence."""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import json
from pathlib import Path
from typing import Any


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def sse_frames(raw: bytes) -> list[dict[str, Any]]:
    normalized = raw.replace(b"\r\n", b"\n")
    frames = []
    for frame in normalized.split(b"\n\n"):
        if not frame:
            continue
        lines = frame.split(b"\n")
        event: str | None = None
        data: list[str] = []
        for line in lines:
            if line.startswith(b"event:"):
                event = line[6:].lstrip().decode("utf-8", errors="replace")
            elif line.startswith(b"data:"):
                data.append(line[5:].lstrip().decode("utf-8", errors="replace"))
        frames.append(
            {
                "data": "\n".join(data),
                "event": event,
                "rawBase64": base64.b64encode(frame).decode(),
            }
        )
    return frames


def sse_record(
    raw: bytes,
    status: int,
    headers: dict[str, str],
    *,
    cancelled: bool = False,
    completed: bool = True,
) -> dict[str, Any]:
    return {
        "bodyBytes": len(raw),
        "bodySha256": hashlib.sha256(raw).hexdigest(),
        "cancelled": cancelled,
        "completed": completed,
        "frames": sse_frames(raw),
        "headers": dict(sorted(headers.items())),
        "rawBase64": base64.b64encode(raw).decode(),
        "status": status,
    }


def transcript_record(
    sent: list[str],
    received: list[str],
    close_code: int | None,
    close_reason: str | None,
) -> dict[str, Any]:
    return {
        "closeCode": close_code,
        "closeReason": close_reason,
        "received": [
            {
                "json": parse_json_or_none(message),
                "raw": message,
            }
            for message in received
        ],
        "sent": [
            {
                "json": parse_json_or_none(message),
                "raw": message,
            }
            for message in sent
        ],
    }


def parse_json_or_none(value: str) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def file_record(
    body: bytes,
    status: int,
    headers: dict[str, str],
    pdf: dict[str, Any] | None = None,
) -> dict[str, Any]:
    tracked_headers = {
        key.lower(): value
        for key, value in headers.items()
        if key.lower()
        in {
            "content-disposition",
            "content-length",
            "content-type",
        }
    }
    return {
        "bodyBytes": len(body),
        "bodySha256": hashlib.sha256(body).hexdigest(),
        "headers": dict(sorted(tracked_headers.items())),
        "pdf": pdf,
        "status": status,
    }


def comparison_report(left: Any, right: Any) -> dict[str, Any]:
    return {
        "left": left,
        "passed": left == right,
        "right": right,
    }


async def capture_websocket(args: argparse.Namespace) -> int:
    import websockets

    sent = [line for line in args.messages.read_text(encoding="utf-8").splitlines() if line]
    received: list[str] = []
    close_code: int | None = None
    close_reason: str | None = None
    async with websockets.connect(
        args.url,
        open_timeout=args.timeout,
        close_timeout=args.timeout,
        max_size=args.max_size,
    ) as websocket:
        for message in sent:
            await websocket.send(message)
        try:
            while len(received) < args.max_messages:
                message = await asyncio.wait_for(
                    websocket.recv(),
                    timeout=args.timeout,
                )
                if not isinstance(message, str):
                    raise RuntimeError("Expected text WebSocket message")
                received.append(message)
        except TimeoutError:
            pass
        close_code = websocket.close_code
        close_reason = websocket.close_reason
    write_json(
        args.output,
        transcript_record(sent, received, close_code, close_reason),
    )
    return 0


def capture_sse(args: argparse.Namespace) -> int:
    import httpx

    body = args.body.read_bytes() if args.body else None
    headers = json.loads(args.headers) if args.headers else {}
    with (
        httpx.Client(timeout=args.timeout) as client,
        client.stream(
            args.method,
            args.url,
            content=body,
            headers=headers,
        ) as response,
    ):
        raw = bytearray()
        cancelled = False
        for chunk in response.iter_raw():
            raw.extend(chunk)
            if args.cancel_after_bytes is not None and len(raw) >= args.cancel_after_bytes:
                cancelled = True
                break
        tracked = {
            key.lower(): value
            for key, value in response.headers.items()
            if key.lower()
            in {
                "content-type",
                "cache-control",
                "connection",
                "x-accel-buffering",
            }
        }
        status = response.status_code
    write_json(
        args.output,
        sse_record(
            bytes(raw),
            status,
            tracked,
            cancelled=cancelled,
            completed=not cancelled,
        ),
    )
    return 0


def capture_file(args: argparse.Namespace) -> int:
    import httpx

    with httpx.Client(timeout=args.timeout) as client:
        response = client.get(args.url)
    pdf_evidence = None
    content_type = response.headers.get("content-type", "")
    if "pdf" in content_type.lower() or args.url.lower().endswith(".pdf"):
        from io import BytesIO

        from pdfminer.high_level import extract_text
        from pypdf import PdfReader

        reader = PdfReader(BytesIO(response.content))
        pdf_evidence = {
            "encrypted": reader.is_encrypted,
            "pageCount": len(reader.pages) if not reader.is_encrypted else None,
            "text": (extract_text(BytesIO(response.content)) if not reader.is_encrypted else None),
        }
    args.body_output.parent.mkdir(parents=True, exist_ok=True)
    args.body_output.write_bytes(response.content)
    write_json(
        args.output,
        file_record(
            response.content,
            response.status_code,
            dict(response.headers),
            pdf_evidence,
        ),
    )
    return 0


def compare(args: argparse.Namespace) -> int:
    left = json.loads(args.left.read_text(encoding="utf-8"))
    right = json.loads(args.right.read_text(encoding="utf-8"))
    report = comparison_report(left, right)
    write_json(args.output, report)
    return 0 if report["passed"] else 1


def parser() -> argparse.ArgumentParser:
    argument_parser = argparse.ArgumentParser()
    subparsers = argument_parser.add_subparsers(dest="command", required=True)

    sse = subparsers.add_parser("capture-sse")
    sse.add_argument("--body", type=Path)
    sse.add_argument("--cancel-after-bytes", type=int)
    sse.add_argument("--headers")
    sse.add_argument("--method", default="POST")
    sse.add_argument("--output", type=Path, required=True)
    sse.add_argument("--timeout", type=float, default=60)
    sse.add_argument("--url", required=True)
    sse.set_defaults(handler=capture_sse)

    websocket = subparsers.add_parser("capture-websocket")
    websocket.add_argument("--max-messages", type=int, default=100)
    websocket.add_argument("--max-size", type=int, default=2 * 1024 * 1024)
    websocket.add_argument("--messages", type=Path, required=True)
    websocket.add_argument("--output", type=Path, required=True)
    websocket.add_argument("--timeout", type=float, default=10)
    websocket.add_argument("--url", required=True)
    websocket.set_defaults(handler=capture_websocket)

    file_parser = subparsers.add_parser("capture-file")
    file_parser.add_argument("--body-output", type=Path, required=True)
    file_parser.add_argument("--output", type=Path, required=True)
    file_parser.add_argument("--timeout", type=float, default=60)
    file_parser.add_argument("--url", required=True)
    file_parser.set_defaults(handler=capture_file)

    compare_parser = subparsers.add_parser("compare")
    compare_parser.add_argument("--left", type=Path, required=True)
    compare_parser.add_argument("--output", type=Path, required=True)
    compare_parser.add_argument("--right", type=Path, required=True)
    compare_parser.set_defaults(handler=compare)
    return argument_parser


def main() -> None:
    args = parser().parse_args()
    handler = args.handler
    result = handler(args)
    if asyncio.iscoroutine(result):
        result = asyncio.run(result)
    raise SystemExit(result)


if __name__ == "__main__":
    main()
