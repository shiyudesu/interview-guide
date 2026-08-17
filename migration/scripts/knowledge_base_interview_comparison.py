#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import psycopg
import redis

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "migration/reports"
MODEL_RECORD = REPORTS / "knowledge-base-interview-model-stub.jsonl"
TASK_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
FIXED_EMBEDDING = [1.0] + [0.0] * 1023


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

    def redis_connection(self, *, decode: bool = True) -> redis.Redis:
        return redis.Redis(
            host="127.0.0.1",
            port=self.redis_port,
            decode_responses=decode,
        )


TARGETS = (
    Target("java", "http://127.0.0.1:18080", 15432, 16379, "interview_guide_java"),
    Target("python", "http://127.0.0.1:28080", 25432, 26379, "interview_guide_python"),
)


def records() -> list[dict[str, Any]]:
    if not MODEL_RECORD.exists():
        return []
    return [
        json.loads(line)
        for line in MODEL_RECORD.read_text(encoding="utf-8").splitlines()
        if line
    ]


def reset_and_seed(target: Target) -> int:
    with target.database_connection() as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            TRUNCATE TABLE
                interview_answers,
                interview_sessions,
                rag_chat_messages,
                rag_session_knowledge_bases,
                rag_chat_sessions,
                knowledge_base_questions,
                vector_store,
                knowledge_bases
            RESTART IDENTITY CASCADE
            """
        )
        cursor.execute(
            """
            UPDATE llm_provider_config
            SET base_url = 'http://127.0.0.1:18100/v1',
                model = 'comparison-model',
                embedding_model = 'comparison-embedding',
                embedding_dimensions = 1024,
                supports_embedding = true,
                enabled = true
            WHERE id = 'dashscope'
            """
        )
        cursor.execute(
            """
            UPDATE llm_global_setting
            SET default_chat_provider_id = 'dashscope',
                default_embedding_provider_id = 'dashscope'
            WHERE id = 1
            """
        )
        cursor.execute(
            """
            INSERT INTO knowledge_bases (
                access_count,
                category,
                chunk_count,
                content_type,
                file_hash,
                file_size,
                last_accessed_at,
                name,
                original_filename,
                question_count,
                uploaded_at,
                vector_status
            )
            VALUES (
                1,
                '迁移比较',
                1,
                'text/plain',
                'knowledge-base-interview-comparison-hash',
                100,
                TIMESTAMP '2026-08-16 08:00:00',
                '知识库专项面试比较',
                'knowledge-base-interview.txt',
                0,
                TIMESTAMP '2026-08-16 08:00:00',
                'COMPLETED'
            )
            RETURNING id
            """
        )
        knowledge_base_id = int(cursor.fetchone()[0])
        cursor.execute(
            """
            INSERT INTO vector_store (content, metadata, embedding)
            VALUES (%s, %s::json, %s::vector)
            """,
            (
                "Redis 支持 RDB 与 AOF；外部模型调用应放在数据库事务之外。",
                json.dumps({"kb_id": str(knowledge_base_id)}),
                "[" + ",".join(str(value) for value in FIXED_EMBEDDING) + "]",
            ),
        )
    client = target.redis_connection()
    keys = list(client.scan_iter("*"))
    if keys:
        client.delete(*keys)
    return knowledge_base_id


def success(response: httpx.Response) -> Any:
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") != 200 or payload.get("success") is not True:
        raise AssertionError(payload)
    return payload.get("data")


def business_error(response: httpx.Response) -> dict[str, Any]:
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") == 200 or payload.get("success") is not False:
        raise AssertionError(payload)
    return payload


def poll_generation(client: httpx.Client, knowledge_base_id: int) -> dict[str, Any]:
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        value = success(
            client.get(
                f"/api/knowledgebase/{knowledge_base_id}/questions/generation-status"
            )
        )
        if value["questionGenStatus"] in {"COMPLETED", "FAILED"}:
            return value
        time.sleep(0.2)
    raise AssertionError("Question generation timed out")


def poll_evaluation(client: httpx.Client, session_id: str) -> dict[str, Any]:
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        value = success(
            client.get(f"/api/interview/sessions/{session_id}/details")
        )
        if value["evaluateStatus"] in {"COMPLETED", "FAILED"}:
            return value
        time.sleep(0.2)
    raise AssertionError("Interview evaluation timed out")


def database_state(target: Target, knowledge_base_id: int, session_id: str) -> dict[str, Any]:
    with target.database_connection() as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT question_gen_status, question_gen_task_id, question_gen_config,
                   question_gen_message, question_gen_saved_count,
                   question_gen_skipped_count, question_gen_error,
                   question_gen_updated_at
            FROM knowledge_bases
            WHERE id = %s
            """,
            (knowledge_base_id,),
        )
        generation = list(cursor.fetchone())
        generation[2] = json.loads(generation[2])
        generation[7] = generation[7].isoformat()
        cursor.execute(
            """
            SELECT id, knowledge_base_id, skill_id, difficulty, type, category,
                   question, topic_summary, reference_answer, key_points_json,
                   scoring_rubric, follow_ups_json, source_context, status,
                   created_at, updated_at
            FROM knowledge_base_questions
            WHERE knowledge_base_id = %s
            ORDER BY id
            """,
            (knowledge_base_id,),
        )
        question_rows = []
        for row in cursor.fetchall():
            values = list(row)
            values[9] = json.loads(values[9]) if values[9] else None
            values[11] = json.loads(values[11]) if values[11] else None
            values[14] = values[14].isoformat()
            values[15] = values[15].isoformat()
            question_rows.append(values)
        cursor.execute(
            """
            SELECT session_id, total_questions, current_question_index, status,
                   evaluate_status, evaluate_error, overall_score,
                   overall_feedback, strengths_json, improvements_json,
                   reference_answers_json, questions_json, skill_id, difficulty,
                   llm_provider, source_type, knowledge_base_id,
                   interview_category, created_at, completed_at
            FROM interview_sessions
            WHERE session_id = %s
            """,
            (session_id,),
        )
        session = list(cursor.fetchone())
        for index in (8, 9, 10, 11):
            session[index] = json.loads(session[index]) if session[index] else None
        session[18] = session[18].isoformat()
        session[19] = session[19].isoformat() if session[19] else None
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
        answers = []
        for row in cursor.fetchall():
            values = list(row)
            values[7] = json.loads(values[7]) if values[7] else None
            values[8] = values[8].isoformat()
            answers.append(values)
    return {
        "generation": generation,
        "questions": question_rows,
        "session": session,
        "answers": answers,
    }


def redis_state(target: Target, session_id: str) -> dict[str, Any]:
    client = target.redis_connection()
    raw_client = target.redis_connection(decode=False)
    session_key = f"interview:session:{session_id}"
    question_pending = client.xpending(
        "knowledgebase:question-gen:stream",
        "question-gen-group",
    )
    evaluation_pending = client.xpending(
        "interview:evaluate:stream",
        "evaluate-group",
    )
    return {
        "cachedSessionExists": raw_client.exists(session_key) == 1,
        "cachedSessionTtlValid": 86_300 <= raw_client.ttl(session_key) <= 86_400,
        "questionStream": [
            fields
            for _, fields in client.xrange("knowledgebase:question-gen:stream")
        ],
        "questionPending": question_pending["pending"],
        "evaluationStream": [
            fields for _, fields in client.xrange("interview:evaluate:stream")
        ],
        "evaluationPending": evaluation_pending["pending"],
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


def model_request_summaries(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summaries = []
    for payload in values:
        if "input" in payload:
            summaries.append(
                {
                    "kind": "embedding",
                    "model": payload.get("model"),
                    "input": payload.get("input"),
                    "dimensions": payload.get("dimensions"),
                    "encodingFormat": payload.get("encoding_format"),
                }
            )
            continue
        messages = payload.get("messages")
        if not isinstance(messages, list) or len(messages) < 2:
            continue
        system = str(messages[0].get("content") or "")
        if "根据知识库内容生成可维护的面试题库草稿" in system:
            kind = "question-generation"
        elif "10 年以上经验" in system:
            kind = "evaluation-batch"
        elif "资深技术面试评审专家" in system:
            kind = "evaluation-summary"
        else:
            continue
        summaries.append(
            {
                "kind": kind,
                "model": payload.get("model"),
                "temperature": payload.get("temperature"),
                "roles": [message.get("role") for message in messages],
                "systemCore": prompt_core(system),
                "user": messages[1].get("content"),
            }
        )
    return summaries


def capture(target: Target, knowledge_base_id: int) -> dict[str, Any]:
    before = len(records())
    with httpx.Client(base_url=target.base_url, timeout=120) as client:
        success(client.post("/api/llm-provider/reload"))
        initial_status = success(
            client.get(
                f"/api/knowledgebase/{knowledge_base_id}/questions/generation-status"
            )
        )
        invalid_generation_count = business_error(
            client.post(
                f"/api/knowledgebase/{knowledge_base_id}/questions/generate",
                json={
                    "questionCount": 0,
                    "followUpCount": 1,
                    "categoryLimit": 3,
                },
            )
        )
        missing_category_limit = business_error(
            client.post(
                f"/api/knowledgebase/{knowledge_base_id}/questions/generate",
                json={
                    "questionCount": 2,
                    "followUpCount": 1,
                },
            )
        )
        invalid_capacity = business_error(
            client.get(
                f"/api/knowledgebase/{knowledge_base_id}/interview-capacity",
                params={
                    "difficulty": "mid",
                    "mainQuestionCount": 0,
                },
            )
        )
        invalid_interview_count = business_error(
            client.post(
                "/api/knowledgebase-interviews/sessions",
                json={
                    "knowledgeBaseId": knowledge_base_id,
                    "mainQuestionCount": 0,
                    "followUpCount": 0,
                },
            )
        )
        queued = success(
            client.post(
                f"/api/knowledgebase/{knowledge_base_id}/questions/generate",
                json={
                    "difficulty": "mid",
                    "questionCount": 2,
                    "followUpCount": 1,
                    "categoryLimit": 3,
                    "llmProvider": "dashscope",
                },
            )
        )
        duplicate_generation = business_error(
            client.post(
                f"/api/knowledgebase/{knowledge_base_id}/questions/generate",
                json={
                    "difficulty": "mid",
                    "questionCount": 2,
                    "followUpCount": 1,
                    "categoryLimit": 3,
                    "llmProvider": "dashscope",
                },
            )
        )
        completed = poll_generation(client, knowledge_base_id)
        if completed["questionGenStatus"] != "COMPLETED":
            raise AssertionError(completed)
        generated = success(
            client.get(f"/api/knowledgebase/{knowledge_base_id}/questions")
        )
        generated_by_question = {item["question"]: item for item in generated}
        redis_question = generated_by_question[
            "请说明 Redis 的两种持久化方式及其取舍。"
        ]
        success(
            client.put(
                f"/api/knowledgebase/questions/{redis_question['id']}/status",
                json={"status": "ACTIVE"},
            )
        )
        created = success(
            client.post(
                f"/api/knowledgebase/{knowledge_base_id}/questions",
                json={
                    "difficulty": "mid",
                    "type": "MANUAL",
                    "category": "手工",
                    "question": "手工问题",
                    "keyPoints": ["手工要点"],
                    "followUps": [{"question": "手工追问"}],
                },
            )
        )
        updated = success(
            client.put(
                f"/api/knowledgebase/questions/{created['id']}",
                json={
                    "category": "手工更新",
                    "question": "手工更新问题",
                    "status": "ARCHIVED",
                },
            )
        )
        filtered = success(
            client.get(
                f"/api/knowledgebase/{knowledge_base_id}/questions",
                params={
                    "status": "ARCHIVED",
                    "category": "手工更新",
                    "difficulty": "mid",
                    "keyword": "更新",
                },
            )
        )
        categories = success(
            client.get(
                f"/api/knowledgebase/{knowledge_base_id}/questions/categories"
            )
        )
        capacity = success(
            client.get(
                f"/api/knowledgebase/{knowledge_base_id}/interview-capacity",
                params={
                    "category": "Redis",
                    "difficulty": "mid",
                    "mainQuestionCount": 1,
                },
            )
        )
        insufficient = business_error(
            client.post(
                "/api/knowledgebase-interviews/sessions",
                json={
                    "knowledgeBaseId": knowledge_base_id,
                    "category": "Redis",
                    "difficulty": "mid",
                    "mainQuestionCount": 2,
                    "followUpCount": 1,
                    "llmProvider": "dashscope",
                },
            )
        )
        interview = success(
            client.post(
                "/api/knowledgebase-interviews/sessions",
                json={
                    "knowledgeBaseId": knowledge_base_id,
                    "category": " Redis ",
                    "difficulty": "mid",
                    "mainQuestionCount": 1,
                    "followUpCount": 1,
                    "llmProvider": "dashscope",
                },
            )
        )
        session_id = interview["sessionId"]
        submissions = []
        for question in interview["questions"]:
            submissions.append(
                success(
                    client.post(
                        f"/api/interview/sessions/{session_id}/answers",
                        json={
                            "questionIndex": question["questionIndex"],
                            "answer": f"固定回答-{question['questionIndex']}",
                        },
                    )
                )
            )
        detail = poll_evaluation(client, session_id)
        if detail["evaluateStatus"] != "COMPLETED":
            raise AssertionError(detail)
        report = success(
            client.get(f"/api/interview/sessions/{session_id}/report")
        )
        success(client.delete(f"/api/knowledgebase/questions/{created['id']}"))
        after_delete = success(
            client.get(f"/api/knowledgebase/{knowledge_base_id}/questions")
        )
    request_records = records()[before:]
    return {
        "initialStatus": initial_status,
        "invalidGenerationCount": invalid_generation_count,
        "missingCategoryLimit": missing_category_limit,
        "invalidCapacity": invalid_capacity,
        "invalidInterviewCount": invalid_interview_count,
        "queued": queued,
        "duplicateGeneration": duplicate_generation,
        "completed": completed,
        "generated": generated,
        "updated": updated,
        "filtered": filtered,
        "categories": categories,
        "capacity": capacity,
        "insufficient": insufficient,
        "interview": interview,
        "submissions": submissions,
        "detail": detail,
        "report": report,
        "afterDelete": after_delete,
        "database": database_state(target, knowledge_base_id, session_id),
        "redis": redis_state(target, session_id),
        "modelRequests": model_request_summaries(request_records),
        "fieldOrder": {
            "status": list(completed),
            "question": list(generated[0]),
            "session": list(interview),
            "interviewQuestion": list(interview["questions"][0]),
            "capacity": list(capacity),
        },
    }


def normalize(document: dict[str, Any]) -> dict[str, Any]:
    value = json.loads(json.dumps(document, ensure_ascii=False))
    value["generated"] = sorted(value["generated"], key=lambda item: item["id"])
    value["afterDelete"] = sorted(value["afterDelete"], key=lambda item: item["id"])
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "phase",
        choices=("prepare", "capture", "all"),
        nargs="?",
        default="all",
    )
    arguments = parser.parse_args()
    REPORTS.mkdir(parents=True, exist_ok=True)
    ids_path = REPORTS / "knowledge-base-interview-ids.json"
    if arguments.phase in {"prepare", "all"}:
        ids = {
            target.name: reset_and_seed(target)
            for target in TARGETS
        }
        ids_path.write_text(
            json.dumps(ids, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if arguments.phase == "prepare":
            print("Knowledge-base interview comparison data prepared")
            return
    else:
        ids = json.loads(ids_path.read_text(encoding="utf-8"))
    results = {}
    for target in TARGETS:
        results[target.name] = capture(target, int(ids[target.name]))
    left = normalize(results["java"])
    right = normalize(results["python"])
    report = {
        "java": results["java"],
        "python": results["python"],
        "equal": left == right,
    }
    (REPORTS / "knowledge-base-interview-comparison.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if left != right:
        raise SystemExit("Knowledge-base interview Java/Python comparison differs")
    print("Knowledge-base interview comparison passed")


if __name__ == "__main__":
    main()
