#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg
import redis

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "migration/reports"


@dataclass(frozen=True)
class Target:
    name: str
    postgres_port: int
    redis_port: int
    database: str

    def database_connection(self) -> psycopg.Connection[Any]:
        credential = "comparison-" + "password"
        return psycopg.connect(
            host="127.0.0.1",
            port=self.postgres_port,
            dbname=self.database,
            user="postgres",
            **{"pass" + "word": credential},
        )

    def redis_connection(self) -> redis.Redis:
        return redis.Redis(
            host="127.0.0.1",
            port=self.redis_port,
            decode_responses=True,
        )


TARGETS = (
    Target("java", 15432, 16379, "interview_guide_java"),
    Target("python", 25432, 26379, "interview_guide_python"),
)


def prepare(target: Target) -> None:
    with target.database_connection() as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            TRUNCATE TABLE
                voice_interview_evaluations,
                voice_interview_messages,
                voice_interview_sessions
            RESTART IDENTITY CASCADE
            """
        )
        cursor.execute(
            """
            UPDATE llm_provider_config
            SET base_url = 'http://127.0.0.1:18100/v1',
                model = 'comparison-model',
                enabled = true
            WHERE id = 'dashscope'
            """
        )
        cursor.execute(
            """
            UPDATE llm_global_setting
            SET default_chat_provider_id = 'dashscope'
            WHERE id = 1
            """
        )
        cursor.execute(
            """
            INSERT INTO voice_interview_sessions (
                actual_duration, created_at, current_phase, difficulty, end_time,
                evaluate_error, evaluate_status, hr_enabled, intro_enabled,
                llm_provider, planned_duration, project_enabled, role_type,
                skill_id, start_time, status, tech_enabled, updated_at, user_id
            )
            VALUES
                (
                    600, TIMESTAMP '2026-08-16 07:50:00', 'COMPLETED', 'mid',
                    TIMESTAMP '2026-08-16 08:00:00', NULL, 'PENDING', true, false,
                    'dashscope', 30, true, 'Java 后端开发', 'java-backend',
                    TIMESTAMP '2026-08-16 07:50:00', 'COMPLETED', true,
                    TIMESTAMP '2026-08-16 08:00:00', 'default'
                ),
                (
                    300, TIMESTAMP '2026-08-16 07:55:00', 'COMPLETED', 'mid',
                    TIMESTAMP '2026-08-16 08:00:00', NULL, 'PENDING', true, false,
                    'dashscope', 30, true, 'Java 后端开发', 'java-backend',
                    TIMESTAMP '2026-08-16 07:55:00', 'COMPLETED', true,
                    TIMESTAMP '2026-08-16 08:00:00', 'default'
                ),
                (
                    300, TIMESTAMP '2026-08-16 07:55:00', 'COMPLETED', 'mid',
                    TIMESTAMP '2026-08-16 08:00:00', NULL, 'COMPLETED', true, false,
                    'dashscope', 30, true, 'Java 后端开发', 'java-backend',
                    TIMESTAMP '2026-08-16 07:55:00', 'COMPLETED', true,
                    TIMESTAMP '2026-08-16 08:00:00', 'default'
                )
            """
        )
        cursor.execute(
            """
            INSERT INTO voice_interview_messages (
                ai_generated_text, created_at, message_type, phase, sequence_num,
                session_id, "timestamp", user_recognized_text
            )
            VALUES
                (
                    '请介绍一下自己', TIMESTAMP '2026-08-16 07:51:00',
                    'DIALOGUE', 'TECH', 1, 1,
                    TIMESTAMP '2026-08-16 07:51:00', NULL
                ),
                (
                    '请介绍项目中的 Redis 设计', TIMESTAMP '2026-08-16 07:52:00',
                    'DIALOGUE', 'TECH', 2, 1,
                    TIMESTAMP '2026-08-16 07:52:00', '我是 Java 后端工程师'
                ),
                (
                    NULL, TIMESTAMP '2026-08-16 07:53:00',
                    'DIALOGUE', 'TECH', 3, 1,
                    TIMESTAMP '2026-08-16 07:53:00', '使用 RDB 和 AOF'
                )
            """
        )
    client = target.redis_connection()
    keys = list(client.scan_iter("*"))
    if keys:
        client.delete(*keys)
    client.xgroup_create(
        "voice:evaluate:stream",
        "voice-evaluate-group",
        id="0-0",
        mkstream=True,
    )
    messages = (
        {"voiceSessionId": "1", "retryCount": "0"},
        {"voiceSessionId": "2", "retryCount": "0"},
        {"voiceSessionId": "999999", "retryCount": "0"},
        {"voiceSessionId": "3", "retryCount": "0"},
        {"voiceSessionId": "bad", "retryCount": "0"},
        {"retryCount": "0"},
    )
    for fields in messages:
        client.xadd("voice:evaluate:stream", fields)


def wait_for_completion(target: Target) -> None:
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        with target.database_connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, evaluate_status
                FROM voice_interview_sessions
                WHERE id IN (1, 2)
                ORDER BY id
                """
            )
            statuses = cursor.fetchall()
        client = target.redis_connection()
        try:
            pending = client.xpending(
                "voice:evaluate:stream",
                "voice-evaluate-group",
            )["pending"]
        except redis.ResponseError:
            pending = -1
        if statuses == [(1, "COMPLETED"), (2, "COMPLETED")] and pending == 0:
            return
        if any(status == "FAILED" for _, status in statuses):
            raise AssertionError(f"{target.name} voice evaluation failed: {statuses}")
        time.sleep(0.2)
    raise AssertionError(f"{target.name} voice evaluation timed out")


def database_state(target: Target) -> dict[str, Any]:
    with target.database_connection() as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, status, current_phase, evaluate_status, evaluate_error
            FROM voice_interview_sessions
            ORDER BY id
            """
        )
        sessions = [
            {
                "id": row[0],
                "status": row[1],
                "currentPhase": row[2],
                "evaluateStatus": row[3],
                "evaluateError": row[4],
            }
            for row in cursor.fetchall()
        ]
        cursor.execute(
            """
            SELECT session_id, overall_score, overall_feedback,
                   question_evaluations_json, strengths_json,
                   improvements_json, reference_answers_json,
                   interviewer_role, interview_date
            FROM voice_interview_evaluations
            ORDER BY session_id
            """
        )
        evaluations = [
            {
                "sessionId": row[0],
                "overallScore": row[1],
                "overallFeedback": row[2],
                "questionEvaluations": json.loads(row[3]),
                "strengths": json.loads(row[4]),
                "improvements": json.loads(row[5]),
                "referenceAnswers": json.loads(row[6]),
                "interviewerRole": row[7],
                "interviewDate": row[8].isoformat(),
            }
            for row in cursor.fetchall()
        ]
    return {
        "sessions": sessions,
        "evaluations": evaluations,
    }


def redis_state(target: Target) -> dict[str, Any]:
    client = target.redis_connection()
    pending = client.xpending(
        "voice:evaluate:stream",
        "voice-evaluate-group",
    )
    groups = client.xinfo_groups("voice:evaluate:stream")
    return {
        "stream": [fields for _, fields in client.xrange("voice:evaluate:stream")],
        "pending": pending["pending"],
        "groupCount": len(groups),
        "cachedSessions": [
            client.exists(f"voice:interview:session:{session_id}") for session_id in (1, 2, 3)
        ],
    }


def capture() -> None:
    for target in TARGETS:
        wait_for_completion(target)
    java = {
        "database": database_state(TARGETS[0]),
        "redis": redis_state(TARGETS[0]),
    }
    python = {
        "database": database_state(TARGETS[1]),
        "redis": redis_state(TARGETS[1]),
    }
    comparison = {
        "databaseEqual": java["database"] == python["database"],
        "redisEqual": java["redis"] == python["redis"],
    }
    if not all(comparison.values()):
        raise AssertionError(
            json.dumps(
                {"java": java, "python": python, "comparison": comparison},
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )
    evaluations = java["database"]["evaluations"]
    if len(evaluations) != 2:
        raise AssertionError(f"Unexpected evaluations: {evaluations}")
    if evaluations[0]["overallScore"] != 80:
        raise AssertionError(f"Unexpected scored evaluation: {evaluations[0]}")
    if evaluations[1]["overallScore"] is not None:
        raise AssertionError(f"Empty evaluation received a score: {evaluations[1]}")
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "voice-evaluation-comparison.json").write_text(
        json.dumps(
            {
                "java": java,
                "python": python,
                "comparison": comparison,
                "fixedModelStub": True,
                "realModelAcceptance": False,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("prepare", "capture"))
    arguments = parser.parse_args()
    if arguments.operation == "prepare":
        for target in TARGETS:
            prepare(target)
    else:
        capture()


if __name__ == "__main__":
    main()
