#!/usr/bin/env python3
"""Capture and compare migration HTTP contracts and PostgreSQL schemas."""

from __future__ import annotations

import argparse
import difflib
import html
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def response_headers(
    response: Any, tracked_headers: list[str]
) -> dict[str, list[str]]:
    return {
        name: response.headers.get_all(name) or []
        for name in tracked_headers
        if response.headers.get_all(name)
    }


def capture_case(
    base_url: str, case: dict[str, Any], tracked_headers: list[str]
) -> dict[str, Any]:
    body = case.get("body")
    data = body.encode("utf-8") if body is not None else None
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{case['path']}",
        data=data,
        headers=case.get("headers", {}),
        method=case["method"],
    )
    try:
        response = urllib.request.urlopen(request, timeout=30)
    except urllib.error.HTTPError as error:
        response = error
    response_body = response.read()
    decoded_body = response_body.decode("utf-8", errors="replace")
    decoded_body = decoded_body.replace(base_url.rstrip("/"), "{{BASE_URL}}")
    return {
        "id": case["id"],
        "request": {
            "body": body,
            "headers": case.get("headers", {}),
            "method": case["method"],
            "path": case["path"],
        },
        "response": {
            "body": decoded_body,
            "headers": response_headers(response, tracked_headers),
            "status": response.status,
        },
    }


def capture_http(base_url: str, cases_document: dict[str, Any]) -> dict[str, Any]:
    tracked_headers = cases_document["trackedResponseHeaders"]
    return {
        "cases": [
            capture_case(base_url, case, tracked_headers)
            for case in cases_document["cases"]
        ],
        "schemaVersion": SCHEMA_VERSION,
    }


def normalize_schema(schema: str) -> str:
    ignored_prefixes = (
        "-- Dumped from database version",
        "-- Dumped by pg_dump version",
        "\\restrict ",
        "\\unrestrict ",
    )
    lines = [
        line.rstrip()
        for line in schema.replace("\r\n", "\n").splitlines()
        if not line.startswith(ignored_prefixes)
    ]
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines) + "\n"


def text_diff(left: str, right: str, left_name: str, right_name: str) -> str:
    return "".join(
        difflib.unified_diff(
            left.splitlines(keepends=True),
            right.splitlines(keepends=True),
            fromfile=left_name,
            tofile=right_name,
        )
    )


def compare_http(
    left: dict[str, Any], right: dict[str, Any]
) -> list[dict[str, Any]]:
    left_cases = {case["id"]: case for case in left["cases"]}
    right_cases = {case["id"]: case for case in right["cases"]}
    differences: list[dict[str, Any]] = []
    for case_id in sorted(left_cases.keys() | right_cases.keys()):
        left_case = left_cases.get(case_id)
        right_case = right_cases.get(case_id)
        if left_case is None or right_case is None:
            differences.append(
                {
                    "caseId": case_id,
                    "kind": "missing-case",
                    "leftPresent": left_case is not None,
                    "rightPresent": right_case is not None,
                }
            )
            continue
        left_response = left_case["response"]
        right_response = right_case["response"]
        if left_response["status"] != right_response["status"]:
            differences.append(
                {
                    "caseId": case_id,
                    "kind": "status",
                    "left": left_response["status"],
                    "right": right_response["status"],
                }
            )
        if left_response["headers"] != right_response["headers"]:
            differences.append(
                {
                    "caseId": case_id,
                    "kind": "headers",
                    "left": left_response["headers"],
                    "right": right_response["headers"],
                }
            )
        if left_response["body"] != right_response["body"]:
            differences.append(
                {
                    "caseId": case_id,
                    "diff": text_diff(
                        left_response["body"],
                        right_response["body"],
                        f"{case_id}:left",
                        f"{case_id}:right",
                    ),
                    "kind": "body",
                }
            )
    return differences


def compare_snapshots(
    left_http: dict[str, Any],
    right_http: dict[str, Any],
    left_schema: str,
    right_schema: str,
    left_state: dict[str, Any] | None = None,
    right_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    http_differences = compare_http(left_http, right_http)
    normalized_left_schema = normalize_schema(left_schema)
    normalized_right_schema = normalize_schema(right_schema)
    schema_equal = normalized_left_schema == normalized_right_schema
    runtime_state_equal = left_state == right_state
    runtime_state_diff = None
    if not runtime_state_equal:
        runtime_state_diff = text_diff(
            json.dumps(left_state, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            json.dumps(right_state, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            "left-runtime-state.json",
            "right-runtime-state.json",
        )
    report = {
        "differences": {
            "databaseSchema": None
            if schema_equal
            else text_diff(
                normalized_left_schema,
                normalized_right_schema,
                "left-schema.sql",
                "right-schema.sql",
            ),
            "http": http_differences,
            "runtimeState": runtime_state_diff,
        },
        "passed": not http_differences and schema_equal and runtime_state_equal,
        "schemaVersion": SCHEMA_VERSION,
        "summary": {
            "differingHttpCaseCount": len(
                {item["caseId"] for item in http_differences}
            ),
            "httpDifferenceCount": len(http_differences),
            "runtimeStateEqual": runtime_state_equal,
            "schemaEqual": schema_equal,
        },
    }
    return report


def write_html_report(path: Path, report: dict[str, Any], title: str) -> None:
    status = "PASS" if report["passed"] else "FAIL"
    http_rows = []
    for difference in report["differences"]["http"]:
        detail = difference.get("diff") or json.dumps(
            {
                key: value
                for key, value in difference.items()
                if key not in {"caseId", "kind"}
            },
            ensure_ascii=False,
            indent=2,
        )
        http_rows.append(
            "<tr>"
            f"<td>{html.escape(difference['caseId'])}</td>"
            f"<td>{html.escape(difference['kind'])}</td>"
            f"<td><pre>{html.escape(detail)}</pre></td>"
            "</tr>"
        )
    schema_diff = report["differences"]["databaseSchema"] or ""
    runtime_state_diff = report["differences"]["runtimeState"] or ""
    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{html.escape(title)}</title>
  <style>
    body {{ font-family: sans-serif; margin: 2rem; }}
    table {{ border-collapse: collapse; width: 100%; }}
    td, th {{ border: 1px solid #ccc; padding: .5rem; vertical-align: top; }}
    pre {{ margin: 0; overflow-x: auto; white-space: pre-wrap; }}
    .pass {{ color: #087f23; }}
    .fail {{ color: #b00020; }}
  </style>
</head>
<body>
  <h1>{html.escape(title)}</h1>
  <p class="{status.lower()}"><strong>{status}</strong></p>
  <p>HTTP differences: {report['summary']['httpDifferenceCount']};
     database schema equal: {str(report['summary']['schemaEqual']).lower()};
     runtime state equal: {str(report['summary']['runtimeStateEqual']).lower()}.</p>
  <h2>HTTP differences</h2>
  <table>
    <thead><tr><th>Case</th><th>Kind</th><th>Detail</th></tr></thead>
    <tbody>{''.join(http_rows)}</tbody>
  </table>
  <h2>Database schema difference</h2>
  <pre>{html.escape(schema_diff)}</pre>
  <h2>Runtime state difference</h2>
  <pre>{html.escape(runtime_state_diff)}</pre>
</body>
</html>
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(document, encoding="utf-8")


def capture_command(args: argparse.Namespace) -> int:
    cases_document = load_json(args.cases)
    write_json(args.output, capture_http(args.url, cases_document))
    return 0


def compare_command(args: argparse.Namespace) -> int:
    if bool(args.left_state) != bool(args.right_state):
        raise ValueError("Both --left-state and --right-state are required together")
    report = compare_snapshots(
        load_json(args.left_http),
        load_json(args.right_http),
        args.left_schema.read_text(encoding="utf-8"),
        args.right_schema.read_text(encoding="utf-8"),
        load_json(args.left_state) if args.left_state else None,
        load_json(args.right_state) if args.right_state else None,
    )
    write_json(args.json_report, report)
    write_html_report(args.html_report, report, args.title)
    return 0 if report["passed"] else 1


def parser() -> argparse.ArgumentParser:
    argument_parser = argparse.ArgumentParser()
    subparsers = argument_parser.add_subparsers(dest="command", required=True)

    capture_parser = subparsers.add_parser("capture-http")
    capture_parser.add_argument("--cases", type=Path, required=True)
    capture_parser.add_argument("--output", type=Path, required=True)
    capture_parser.add_argument("--url", required=True)
    capture_parser.set_defaults(handler=capture_command)

    compare_parser = subparsers.add_parser("compare")
    compare_parser.add_argument("--html-report", type=Path, required=True)
    compare_parser.add_argument("--json-report", type=Path, required=True)
    compare_parser.add_argument("--left-http", type=Path, required=True)
    compare_parser.add_argument("--left-schema", type=Path, required=True)
    compare_parser.add_argument("--left-state", type=Path)
    compare_parser.add_argument("--right-http", type=Path, required=True)
    compare_parser.add_argument("--right-schema", type=Path, required=True)
    compare_parser.add_argument("--right-state", type=Path)
    compare_parser.add_argument("--title", default="Migration comparison")
    compare_parser.set_defaults(handler=compare_command)
    return argument_parser


def main() -> None:
    arguments = parser().parse_args()
    raise SystemExit(arguments.handler(arguments))


if __name__ == "__main__":
    main()
