#!/usr/bin/env python3
"""Run deterministic Java/Python interview schedule contract flows."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import psycopg

from comparison import (
    capture_case,
    compare_snapshots,
    write_html_report,
    write_json,
)

TRACKED_HEADERS = [
    "content-type",
    "vary",
]

FLOW = (
    {
        "body": json.dumps(
            {
                "rawText": (
                    "飞书 公司：字节跳动 岗位：Java工程师 "
                    "时间：2026-08-20 10:30 第2轮 "
                    "https://meeting.feishu.cn/fixed"
                ),
                "source": "feishu",
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        "headers": {"Content-Type": "application/json"},
        "id": "schedule-parse-feishu",
        "method": "POST",
        "path": "/api/interview-schedule/parse",
    },
    {
        "body": json.dumps(
            {
                "rawText": (
                    "公司：字节跳动 岗位：Java工程师 "
                    "时间：2026-08-20 10:30 第二轮"
                ),
                "source": "feishu",
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        "headers": {"Content-Type": "application/json"},
        "id": "schedule-parse-chinese-round",
        "method": "POST",
        "path": "/api/interview-schedule/parse",
    },
    {
        "body": json.dumps(
            {
                "rawText": (
                    "腾讯会议 公司：腾讯 岗位：后端工程师 "
                    "2026-08-20 10:30 会议号：123456789 密码：1234"
                ),
                "source": "tencent",
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        "headers": {"Content-Type": "application/json"},
        "id": "schedule-parse-tencent",
        "method": "POST",
        "path": "/api/interview-schedule/parse",
    },
    {
        "body": json.dumps(
            {
                "rawText": (
                    "Zoom 2026-08-20 10:30 "
                    "https://zoom.us/j/123456789"
                ),
                "source": "zoom",
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        "headers": {"Content-Type": "application/json"},
        "id": "schedule-parse-zoom-failure",
        "method": "POST",
        "path": "/api/interview-schedule/parse",
    },
    {
        "id": "schedule-list",
        "method": "GET",
        "path": "/api/interview-schedule",
    },
    {
        "id": "schedule-detail",
        "method": "GET",
        "path": "/api/interview-schedule/1001",
    },
    {
        "id": "schedule-not-found",
        "method": "GET",
        "path": "/api/interview-schedule/999999",
    },
    {
        "body": (
            '{"companyName":"Comparison Corp",'
            '"interviewTime":"2026-08-20T10:30:00"}'
        ),
        "headers": {"Content-Type": "application/json"},
        "id": "schedule-validation-error",
        "method": "POST",
        "path": "/api/interview-schedule",
    },
    {
        "body": json.dumps(
            {
                "companyName": "CRUD Corp",
                "position": "Engineer",
                "interviewTime": "2026-08-22T09:15",
                "interviewType": "VIDEO",
                "roundNumber": 1,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        "headers": {"Content-Type": "application/json"},
        "id": "schedule-create",
        "method": "POST",
        "path": "/api/interview-schedule",
    },
    {
        "body": json.dumps(
            {
                "companyName": "CRUD Corp Updated",
                "position": "Senior Engineer",
                "interviewTime": "2026-08-23T10:20:30",
                "interviewType": "ONSITE",
                "roundNumber": 2,
                "notes": "fixed",
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        "headers": {"Content-Type": "application/json"},
        "id": "schedule-update",
        "method": "PUT",
        "path": "/api/interview-schedule/1002",
    },
    {
        "id": "schedule-patch-status",
        "method": "PATCH",
        "path": "/api/interview-schedule/1002/status?status=COMPLETED",
    },
    {
        "id": "schedule-put-status",
        "method": "PUT",
        "path": "/api/interview-schedule/1002/status?status=RESCHEDULED",
    },
    {
        "id": "schedule-filter",
        "method": "GET",
        "path": "/api/interview-schedule?status=RESCHEDULED",
    },
    {
        "id": "schedule-delete",
        "method": "DELETE",
        "path": "/api/interview-schedule/1002",
    },
)


def capture_flow(base_url: str) -> dict[str, Any]:
    return {
        "cases": [
            capture_case(base_url, case, TRACKED_HEADERS)
            for case in FLOW
        ],
        "schemaVersion": 1,
    }


def database_state(dsn: str) -> dict[str, Any]:
    with psycopg.connect(dsn) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, company_name, created_at, interview_time,
                       interview_type, interviewer, meeting_link, notes,
                       position, round_number, status, updated_at
                FROM interview_schedule
                ORDER BY id
                """
            )
            rows = [
                [
                    value.isoformat(timespec="seconds")
                    if hasattr(value, "isoformat")
                    else value
                    for value in row
                ]
                for row in cursor.fetchall()
            ]
    return {"interviewSchedule": rows}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--java-url", default="http://127.0.0.1:18080")
    parser.add_argument("--python-url", default="http://127.0.0.1:28080")
    parser.add_argument(
        "--java-dsn",
        default=(
            "postgresql://postgres:comparison-password@127.0.0.1:15432/"
            "interview_guide_java"
        ),
    )
    parser.add_argument(
        "--python-dsn",
        default=(
            "postgresql://postgres:comparison-password@127.0.0.1:25432/"
            "interview_guide_python"
        ),
    )
    parser.add_argument("--report-dir", type=Path, required=True)
    args = parser.parse_args()

    left_http = capture_flow(args.java_url)
    right_http = capture_flow(args.python_url)
    report = compare_snapshots(
        left_http,
        right_http,
        "",
        "",
        database_state(args.java_dsn),
        database_state(args.python_dsn),
    )
    write_json(args.report_dir / "interview-schedule-comparison.json", report)
    write_html_report(
        args.report_dir / "interview-schedule-comparison.html",
        report,
        "Interview schedule Java/Python comparison",
    )
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
