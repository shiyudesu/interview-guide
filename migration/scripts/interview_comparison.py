#!/usr/bin/env python3
from __future__ import annotations

import json
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

import httpx
import psycopg
import redis
from pdfminer.high_level import extract_text

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "migration/reports"
MODEL_RECORD = REPORTS / "interview-model-stub.jsonl"


@dataclass(frozen=True)
class Target:
    name: str
    base_url: str
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
    Target("java", "http://127.0.0.1:18080", 15432, 16379, "interview_guide_java"),
    Target("python", "http://127.0.0.1:28080", 25432, 26379, "interview_guide_python"),
)


def reset(target: Target) -> None:
    with target.database_connection() as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            TRUNCATE TABLE interview_answers, interview_sessions, resume_analyses, resumes
            RESTART IDENTITY CASCADE
            """
        )
        cursor.execute(
            """
            UPDATE llm_provider_config
            SET base_url = 'http://127.0.0.1:18100/v1'
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
    client = target.redis_connection()
    keys = list(client.scan_iter("interview:*"))
    keys.extend(client.scan_iter("ratelimit:{InterviewController:*"))
    keys.extend(client.scan_iter("ratelimit:{InterviewSkillController:*"))
    if keys:
        client.delete(*keys)


def result(response: httpx.Response) -> dict[str, Any]:
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") != 200 or payload.get("success") is not True:
        raise AssertionError(payload)
    return payload


def business_error(response: httpx.Response) -> dict[str, Any]:
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") == 200 or payload.get("success") is not False:
        raise AssertionError(payload)
    return payload


def database_state(target: Target, session_id: str) -> dict[str, Any]:
    with target.database_connection() as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT request_id, session_id, total_questions, current_question_index,
                   status, evaluate_status, evaluate_error, overall_score,
                   overall_feedback, strengths_json, improvements_json,
                   reference_answers_json, questions_json, skill_id, difficulty,
                   llm_provider, source_type, resume_id, knowledge_base_id,
                   interview_category, created_at, completed_at
            FROM interview_sessions
            WHERE session_id = %s
            """,
            (session_id,),
        )
        session = cursor.fetchone()
        cursor.execute(
            """
            SELECT question_index, question, category, user_answer, score, feedback,
                   reference_answer, key_points_json, answered_at
            FROM interview_answers AS answer
            JOIN interview_sessions AS session ON session.id = answer.session_id
            WHERE session.session_id = %s
            ORDER BY question_index
            """,
            (session_id,),
        )
        answers = cursor.fetchall()
    if session is None:
        return {"session": None, "answers": []}
    session_values = list(session)
    for index in (9, 10, 11, 12):
        if session_values[index] is not None:
            session_values[index] = json.loads(session_values[index])
    for index in (20, 21):
        if session_values[index] is not None:
            session_values[index] = session_values[index].isoformat()
    answer_values: list[list[Any]] = []
    for answer in answers:
        values = list(answer)
        if values[7] is not None:
            values[7] = json.loads(values[7])
        values[8] = values[8].isoformat()
        answer_values.append(values)
    return {"session": session_values, "answers": answer_values}


def redis_state(target: Target, session_id: str, request_id: str) -> dict[str, Any]:
    client = redis.Redis(
        host="127.0.0.1",
        port=target.redis_port,
        decode_responses=False,
    )
    session_key = f"interview:session:{session_id}"
    result_key = f"interview:create:result:{request_id}"
    stream = client.xrange("interview:evaluate:stream")
    return {
        "sessionExists": client.exists(session_key) == 1,
        "sessionTtlValid": 86_300 <= client.ttl(session_key) <= 86_400,
        "createResultExists": client.exists(result_key) == 1,
        "createResultTtlValid": 86_300 <= client.ttl(result_key) <= 86_400,
        "stream": [
            {key.decode(): value.decode() for key, value in fields.items()} for _, fields in stream
        ],
    }


def prompt_core(value: str) -> str:
    core = value.split("\n\n# 安全边界", 1)[0]
    for marker in (
        "\n\nYour response should be in JSON format.",
        "\n\nThe output should be formatted",
        "\n\n```json",
        '\n\n{"$defs"',
        '\n\n{"properties"',
    ):
        core = core.split(marker, 1)[0]
    return core.rstrip()


def prompt_records(start: int, end: int) -> list[dict[str, Any]]:
    lines = MODEL_RECORD.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines[start:end]]


def run_flow(target: Target) -> tuple[dict[str, Any], int, int]:
    request_id = "comparison-request-0001"
    start_records = len(MODEL_RECORD.read_text(encoding="utf-8").splitlines())
    with httpx.Client(base_url=target.base_url, timeout=60) as client:
        result(client.post("/api/llm-provider/reload"))
        invalid_request_id = business_error(
            client.post(
                "/api/interview/sessions",
                json={
                    "resumeText": "",
                    "questionCount": 3,
                    "forceCreate": True,
                    "llmProvider": "dashscope",
                    "skillId": "java-backend",
                    "difficulty": "mid",
                    "requestId": "bad",
                },
            )
        )
        create_body = {
            "resumeText": "",
            "questionCount": 3,
            "forceCreate": True,
            "llmProvider": "dashscope",
            "skillId": "java-backend",
            "difficulty": "mid",
            "requestId": request_id,
        }
        created = result(client.post("/api/interview/sessions", json=create_body))["data"]
        duplicate = result(client.post("/api/interview/sessions", json=create_body))["data"]
        session_id = created["sessionId"]
        listed = result(client.get("/api/interview/sessions"))["data"]
        fetched = result(client.get(f"/api/interview/sessions/{session_id}"))["data"]
        current = result(client.get(f"/api/interview/sessions/{session_id}/question"))["data"]
        result(
            client.put(
                f"/api/interview/sessions/{session_id}/answers",
                json={"questionIndex": 0, "answer": "固定暂存答案"},
            )
        )
        submissions: list[dict[str, Any]] = []
        for index in range(created["totalQuestions"]):
            submissions.append(
                result(
                    client.post(
                        f"/api/interview/sessions/{session_id}/answers",
                        json={
                            "questionIndex": index,
                            "answer": f"固定提交答案{index + 1}",
                        },
                    )
                )["data"]
            )
        already_completed = business_error(
            client.post(f"/api/interview/sessions/{session_id}/complete")
        )
        invalid_question = business_error(
            client.post(
                f"/api/interview/sessions/{session_id}/answers",
                json={"questionIndex": 99, "answer": "无效"},
            )
        )
        missing = business_error(client.get("/api/interview/sessions/missing-session"))
        report = result(client.get(f"/api/interview/sessions/{session_id}/report"))["data"]
        detail = result(client.get(f"/api/interview/sessions/{session_id}/details"))["data"]
        pdf_response = client.get(f"/api/interview/sessions/{session_id}/export")
        pdf_response.raise_for_status()
        pdf_visible = "".join(extract_text(BytesIO(pdf_response.content)).split())
        database = database_state(target, session_id)
        redis_document = redis_state(target, session_id, request_id)
        result(client.delete(f"/api/interview/sessions/{session_id}"))
        stale_after_delete = result(client.get(f"/api/interview/sessions/{session_id}"))["data"]
        list_after_delete = result(client.get("/api/interview/sessions"))["data"]
        database_after_delete = database_state(target, session_id)
        jd_text = (
            "Java 后端工程师，要求熟悉 Spring、MySQL、Redis，"
            "具备高并发系统设计、性能优化和线上故障排查经验。"
        )
        parsed_jd = result(
            client.post(
                "/api/interview/skills/parse-jd",
                json={"jdText": jd_text},
            )
        )["data"]
        resume_created = result(
            client.post(
                "/api/interview/sessions",
                json={
                    "resumeText": "负责交易系统开发，使用 Java、MySQL 和 Redis。",
                    "questionCount": 3,
                    "forceCreate": True,
                    "llmProvider": "dashscope",
                    "skillId": "java-backend",
                    "difficulty": "mid",
                    "requestId": "comparison-resume-request",
                },
            )
        )["data"]
        result(client.delete(f"/api/interview/sessions/{resume_created['sessionId']}"))
        custom_created = result(
            client.post(
                "/api/interview/sessions",
                json={
                    "resumeText": "",
                    "questionCount": 3,
                    "forceCreate": True,
                    "llmProvider": "dashscope",
                    "skillId": "custom",
                    "difficulty": "mid",
                    "customCategories": parsed_jd,
                    "jdText": jd_text,
                    "requestId": "comparison-custom-request",
                },
            )
        )["data"]
        result(client.delete(f"/api/interview/sessions/{custom_created['sessionId']}"))
    end_records = len(MODEL_RECORD.read_text(encoding="utf-8").splitlines())
    return (
        {
            "invalidRequestId": invalid_request_id,
            "created": created,
            "duplicate": duplicate,
            "listed": listed,
            "fetched": fetched,
            "current": current,
            "submissions": submissions,
            "alreadyCompleted": already_completed,
            "invalidQuestion": invalid_question,
            "missing": missing,
            "report": report,
            "detail": detail,
            "pdf": {
                "contentDisposition": pdf_response.headers.get("content-disposition"),
                "contentType": pdf_response.headers.get("content-type"),
                "visibleText": pdf_visible,
            },
            "database": database,
            "redis": redis_document,
            "staleAfterDelete": stale_after_delete,
            "listAfterDelete": list_after_delete,
            "databaseAfterDelete": database_after_delete,
            "generatedBranches": {
                "parsedJd": parsed_jd,
                "resumeQuestions": resume_created["questions"],
                "customQuestions": custom_created["questions"],
            },
        },
        start_records,
        end_records,
    )


def compare_prompts(
    java_records: list[dict[str, Any]],
    python_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if len(java_records) != len(python_records):
        raise AssertionError(
            f"Model call count differs: java={len(java_records)}, python={len(python_records)}"
        )

    def signature(record: dict[str, Any]) -> tuple[str, str, str, str]:
        messages = record["messages"]
        return (
            str(record.get("model")),
            str(record.get("temperature")),
            prompt_core(messages[0]["content"]),
            messages[1]["content"],
        )

    java_records = sorted(java_records, key=signature)
    python_records = sorted(python_records, key=signature)
    compared: list[dict[str, Any]] = []
    for index, (java, python) in enumerate(zip(java_records, python_records, strict=True)):
        java_messages = java["messages"]
        python_messages = python["messages"]
        item = {
            "index": index,
            "modelEqual": java.get("model") == python.get("model"),
            "temperatureEqual": java.get("temperature") == python.get("temperature"),
            "rolesEqual": [value["role"] for value in java_messages]
            == [value["role"] for value in python_messages],
            "toolsEqual": java.get("tools", []) == python.get("tools", []),
            "systemCoreEqual": prompt_core(java_messages[0]["content"])
            == prompt_core(python_messages[0]["content"]),
            "userPromptEqual": java_messages[1]["content"] == python_messages[1]["content"],
        }
        if not all(value for key, value in item.items() if key != "index"):
            raise AssertionError(f"Model request differs: {item}")
        compared.append(item)
    return compared


def main() -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    for target in TARGETS:
        reset(target)
    java, java_start, java_end = run_flow(TARGETS[0])
    python, python_start, python_end = run_flow(TARGETS[1])
    if java != python:
        output = {"java": java, "python": python}
        (REPORTS / "interview-comparison-failure.json").write_text(
            json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        raise SystemExit("Interview Java/Python comparison differs")
    prompts = compare_prompts(
        prompt_records(java_start, java_end),
        prompt_records(python_start, python_end),
    )
    (REPORTS / "interview-comparison.json").write_text(
        json.dumps(
            {"result": java, "modelRequests": prompts},
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print("Interview comparison passed")


if __name__ == "__main__":
    main()
