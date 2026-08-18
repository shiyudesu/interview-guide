#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg
import redis
from model_record_reader import read_jsonl_records

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "migration/reports"
MODEL_RECORDS = REPORTS / "model-proxy.jsonl"
STATE = REPORTS / "runtime/real-model-voice-evaluation.json"


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


def record_lines() -> list[dict[str, Any]]:
    return read_jsonl_records(MODEL_RECORDS)


def prepare_target(target: Target) -> int:
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
            INSERT INTO voice_interview_sessions (
                actual_duration, created_at, current_phase, difficulty, end_time,
                evaluate_error, evaluate_status, hr_enabled, intro_enabled,
                llm_provider, planned_duration, project_enabled, role_type,
                skill_id, start_time, status, tech_enabled, updated_at, user_id
            )
            VALUES (
                600, TIMESTAMP '2026-08-16 07:50:00', 'COMPLETED', 'mid',
                TIMESTAMP '2026-08-16 08:00:00', NULL, 'PENDING', true, false,
                'dashscope', 30, true, 'Java 后端开发', 'java-backend',
                TIMESTAMP '2026-08-16 07:50:00', 'COMPLETED', true,
                TIMESTAMP '2026-08-16 08:00:00', 'default'
            )
            RETURNING id
            """
        )
        session_id = int(cursor.fetchone()[0])
        cursor.execute(
            """
            INSERT INTO voice_interview_messages (
                ai_generated_text, created_at, message_type, phase, sequence_num,
                session_id, "timestamp", user_recognized_text
            )
            VALUES
                (
                    '请介绍一下自己，并说明最擅长的后端方向。',
                    TIMESTAMP '2026-08-16 07:51:00', 'DIALOGUE', 'TECH', 1, %s,
                    TIMESTAMP '2026-08-16 07:51:00', NULL
                ),
                (
                    '请说明 Redis 持久化方案及其取舍。',
                    TIMESTAMP '2026-08-16 07:52:00', 'DIALOGUE', 'TECH', 2, %s,
                    TIMESTAMP '2026-08-16 07:52:00',
                    '我主要负责 Java 后端，熟悉事务、缓存和故障排查。'
                ),
                (
                    NULL, TIMESTAMP '2026-08-16 07:53:00',
                    'DIALOGUE', 'TECH', 3, %s,
                    TIMESTAMP '2026-08-16 07:53:00',
                    'RDB 恢复快，AOF 数据更完整，生产中会按恢复目标组合使用。'
                )
            """,
            (session_id, session_id, session_id),
        )
    client = target.redis_connection()
    client.delete(
        "voice:evaluate:stream",
        "interview:evaluate:stream",
        "knowledgebase:question-gen:stream",
        "knowledgebase:vectorize:stream",
        "resume:analyze:stream",
    )
    client.xgroup_create(
        "voice:evaluate:stream",
        "voice-evaluate-group",
        id="0-0",
        mkstream=True,
    )
    client.xadd(
        "voice:evaluate:stream",
        {"voiceSessionId": str(session_id), "retryCount": "0"},
    )
    return session_id


def prepare() -> None:
    session_ids = {target.name: prepare_target(target) for target in TARGETS}
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(
        json.dumps(
            {
                "modelRecordOffset": len(record_lines()),
                "sessionIds": session_ids,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def wait_for_evaluation(target: Target, session_id: int) -> None:
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        with target.database_connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT evaluate_status, evaluate_error
                FROM voice_interview_sessions
                WHERE id = %s
                """,
                (session_id,),
            )
            state = cursor.fetchone()
        if state is None:
            raise AssertionError(f"Missing {target.name} voice session")
        if state[0] == "COMPLETED":
            return
        if state[0] == "FAILED":
            raise AssertionError(f"{target.name} real voice evaluation failed: {state[1]}")
        time.sleep(0.5)
    raise AssertionError(f"{target.name} real voice evaluation timed out")


def database_state(target: Target, session_id: int) -> dict[str, Any]:
    with target.database_connection() as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT evaluate_status, evaluate_error
            FROM voice_interview_sessions
            WHERE id = %s
            """,
            (session_id,),
        )
        session = cursor.fetchone()
        cursor.execute(
            """
            SELECT overall_score, overall_feedback, question_evaluations_json,
                   strengths_json, improvements_json, reference_answers_json
            FROM voice_interview_evaluations
            WHERE session_id = %s
            """,
            (session_id,),
        )
        evaluation = cursor.fetchone()
    if session is None or evaluation is None:
        raise AssertionError(f"Missing {target.name} real voice evaluation")
    question_evaluations = json.loads(evaluation[2])
    strengths = json.loads(evaluation[3])
    improvements = json.loads(evaluation[4])
    reference_answers = json.loads(evaluation[5])
    if not isinstance(evaluation[0], int) or not 0 <= evaluation[0] <= 100:
        raise AssertionError(f"Invalid {target.name} overall score: {evaluation[0]}")
    if len(question_evaluations) != 2 or len(reference_answers) != 2:
        raise AssertionError(
            f"Invalid {target.name} voice evaluation details: "
            f"{question_evaluations}, {reference_answers}"
        )
    if any(
        item.get("feedback") == "该题未成功生成评估结果，系统按 0 分处理。"
        for item in question_evaluations
    ):
        raise AssertionError(f"{target.name} real batch evaluation used failure fallback")
    if any(
        set(item)
        != {
            "questionIndex",
            "question",
            "category",
            "userAnswer",
            "score",
            "feedback",
        }
        for item in question_evaluations
    ):
        raise AssertionError(f"Unexpected {target.name} question evaluation schema")
    if any(
        set(item) != {"questionIndex", "question", "referenceAnswer", "keyPoints"}
        for item in reference_answers
    ):
        raise AssertionError(f"Unexpected {target.name} reference answer schema")
    pending = target.redis_connection().xpending(
        "voice:evaluate:stream",
        "voice-evaluate-group",
    )["pending"]
    if pending != 0:
        raise AssertionError(f"{target.name} voice evaluation pending={pending}")
    return {
        "evaluateStatus": session[0],
        "evaluateError": session[1],
        "overallScore": evaluation[0],
        "overallFeedbackLength": len(evaluation[1] or ""),
        "questionCount": len(question_evaluations),
        "strengthCount": len(strengths),
        "improvementCount": len(improvements),
        "referenceAnswerCount": len(reference_answers),
        "redisPending": pending,
    }


def prompt_core(value: str) -> str:
    for marker in (
        "\n\nYour response should be in JSON format.",
        "\n\nThe output should be formatted",
        "\n\n```json",
        '\n\n{"$defs"',
        '\n\n{"properties"',
    ):
        value = value.split(marker, 1)[0]
    return value.rstrip()


def runtime_name(record: dict[str, Any]) -> str | None:
    headers = record.get("headers") or {}
    languages = headers.get("x-stainless-lang") or []
    if languages:
        return str(languages[0])
    user_agents = headers.get("user-agent") or []
    if user_agents and "Java" in str(user_agents[0]):
        return "java"
    if user_agents:
        return "python"
    return None


def model_calls(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    responses = {
        record.get("correlationId"): record
        for record in records
        if record.get("kind") == "http-response"
    }
    calls: dict[str, list[dict[str, Any]]] = {"java": [], "python": []}
    for record in records:
        if record.get("kind") != "http-request":
            continue
        body = record.get("body") or {}
        payload = body.get("json")
        if not isinstance(payload, dict):
            continue
        messages = payload.get("messages")
        if not isinstance(messages, list) or len(messages) < 2:
            continue
        system = str(messages[0].get("content") or "")
        if "10 年以上经验" in system:
            kind = "evaluation-batch"
        elif "资深技术面试评审专家" in system:
            kind = "evaluation-summary"
        else:
            continue
        runtime = runtime_name(record)
        if runtime not in calls:
            continue
        response = responses.get(record.get("correlationId"), {})
        response_body = response.get("body") or {}
        response_json = response_body.get("json") or {}
        calls[runtime].append(
            {
                "kind": kind,
                "calledAt": record.get("recordedAt"),
                "model": payload.get("model"),
                "temperature": payload.get("temperature"),
                "roles": [message.get("role") for message in messages],
                "toolNames": [
                    tool.get("function", {}).get("name")
                    for tool in payload.get("tools", [])
                    if isinstance(tool, dict)
                ],
                "systemCoreSha256": hashlib.sha256(prompt_core(system).encode()).hexdigest(),
                "userPromptSha256": hashlib.sha256(
                    str(messages[1].get("content") or "").encode()
                ).hexdigest(),
                "durationMs": response.get("durationMs"),
                "usage": response_json.get("usage"),
                "cost": {
                    "amount": None,
                    "currency": None,
                    "status": "provider-response-does-not-expose-billing-amount",
                },
            }
        )
    return calls


def validate_calls(calls: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    for runtime in ("java", "python"):
        kinds = [call["kind"] for call in calls[runtime]]
        if "evaluation-batch" not in kinds or "evaluation-summary" not in kinds:
            raise AssertionError(f"Missing {runtime} real voice model calls: {kinds}")
        if any(call["toolNames"] != ["Skill"] for call in calls[runtime]):
            raise AssertionError(f"{runtime} voice evaluation did not use Skill tool")
        if any(not isinstance(call["usage"], dict) for call in calls[runtime]):
            raise AssertionError(f"Missing {runtime} real voice token usage")
    java_batch = next(call for call in calls["java"] if call["kind"] == "evaluation-batch")
    python_batch = next(call for call in calls["python"] if call["kind"] == "evaluation-batch")
    keys = (
        "model",
        "temperature",
        "roles",
        "toolNames",
        "systemCoreSha256",
        "userPromptSha256",
    )
    comparison = {f"{key}Equal": java_batch[key] == python_batch[key] for key in keys}
    java_summary = next(call for call in calls["java"] if call["kind"] == "evaluation-summary")
    python_summary = next(call for call in calls["python"] if call["kind"] == "evaluation-summary")
    for key in (
        "model",
        "temperature",
        "roles",
        "toolNames",
        "systemCoreSha256",
    ):
        comparison[f"summary{key[0].upper()}{key[1:]}Equal"] = (
            java_summary[key] == python_summary[key]
        )
    if not all(comparison.values()):
        raise AssertionError(f"Real voice evaluation batch request differs: {comparison}")
    return comparison


def capture() -> None:
    state = json.loads(STATE.read_text(encoding="utf-8"))
    session_ids = state["sessionIds"]
    for target in TARGETS:
        wait_for_evaluation(target, int(session_ids[target.name]))
    database = {
        target.name: database_state(target, int(session_ids[target.name])) for target in TARGETS
    }
    records = record_lines()[int(state["modelRecordOffset"]) :]
    calls = model_calls(records)
    comparison = validate_calls(calls)
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "real-model-voice-evaluation.json").write_text(
        json.dumps(
            {
                "provider": "dashscope",
                "realModelVerified": True,
                "database": database,
                "calls": calls,
                "requestComparison": comparison,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print("Real model voice evaluation check passed")


def main() -> None:
    if not os.getenv("AI_BAILIAN_API_KEY", "").strip():
        raise SystemExit("AI_BAILIAN_API_KEY is required; real-model verification was not run")
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("prepare", "capture"))
    arguments = parser.parse_args()
    if arguments.operation == "prepare":
        prepare()
    else:
        capture()


if __name__ == "__main__":
    main()
