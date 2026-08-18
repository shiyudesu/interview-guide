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

import httpx
import psycopg
import redis
from model_record_reader import read_jsonl_records

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "migration/reports"
MODEL_RECORDS = REPORTS / "model-proxy.jsonl"
CONTEXT = (
    "Redis 持久化包括 RDB 快照和 AOF 命令日志。RDB 恢复快但可能丢失最近数据，"
    "AOF 数据安全性更高但文件更大。外部模型调用不应放在长数据库事务内，"
    "应使用状态机、幂等任务和恢复机制保持结果一致。"
)
EMBEDDING_MODEL = os.getenv("AI_EMBEDDING_MODEL", "qwen3.7-text-embedding")


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


def records() -> list[dict[str, Any]]:
    return read_jsonl_records(MODEL_RECORDS)


def embed_context(api_key: str) -> list[float]:
    response = httpx.post(
        "http://127.0.0.1:18090/proxy/https/dashscope.aliyuncs.com/compatible-mode/v1/embeddings",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": EMBEDDING_MODEL,
            "input": [CONTEXT],
            "dimensions": 1024,
        },
        timeout=60,
    )
    response.raise_for_status()
    values = [float(value) for value in response.json()["data"][0]["embedding"]]
    if len(values) != 1024:
        raise AssertionError(f"Expected 1024 dimensions, got {len(values)}")
    return values


def reset_and_seed(target: Target, embedding: list[float]) -> int:
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
            INSERT INTO knowledge_bases (
                access_count, chunk_count, content_type, file_hash, file_size,
                name, original_filename, question_count, uploaded_at, vector_status
            )
            VALUES (
                1, 1, 'text/plain', %s, %s, '真实模型专项面试知识库',
                'real-model-specialized-interview.txt', 0,
                TIMESTAMP '2026-08-16 08:00:00', 'COMPLETED'
            )
            RETURNING id
            """,
            (hashlib.sha256(CONTEXT.encode()).hexdigest(), len(CONTEXT.encode())),
        )
        knowledge_base_id = int(cursor.fetchone()[0])
        cursor.execute(
            """
            INSERT INTO vector_store (content, metadata, embedding)
            VALUES (%s, %s::json, %s::vector)
            """,
            (
                CONTEXT,
                json.dumps({"kb_id": str(knowledge_base_id)}),
                "[" + ",".join(str(value) for value in embedding) + "]",
            ),
        )
    client = target.redis_connection()
    keys = list(client.scan_iter("knowledgebase:question-gen:*"))
    keys.extend(client.scan_iter("interview:*"))
    keys.extend(client.scan_iter("ratelimit:{KnowledgeBaseInterviewController:*"))
    if keys:
        client.delete(*keys)
    return knowledge_base_id


def success(response: httpx.Response) -> Any:
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") != 200 or payload.get("success") is not True:
        raise AssertionError(payload)
    return payload.get("data")


def poll_generation(client: httpx.Client, knowledge_base_id: int) -> dict[str, Any]:
    deadline = time.monotonic() + 600
    last_value: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        value = success(
            client.get(
                f"/api/knowledgebase/{knowledge_base_id}/questions/generation-status"
            )
        )
        last_value = value
        if value["questionGenStatus"] in {"COMPLETED", "FAILED"}:
            return value
        time.sleep(1)
    raise AssertionError(f"Real question generation timed out: {last_value}")


def request_summaries(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summaries = []
    for record in values:
        if record.get("kind") != "http-request":
            continue
        payload = (record.get("body") or {}).get("json")
        if not isinstance(payload, dict):
            continue
        upstream = str(record.get("upstream") or "")
        if upstream.endswith("/embeddings"):
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
        if "根据知识库内容生成可维护的面试题库草稿" not in system:
            continue
        summaries.append(
            {
                "kind": "question-generation",
                "model": payload.get("model"),
                "temperature": payload.get("temperature"),
                "roles": [message.get("role") for message in messages],
                "system": system,
                "user": messages[1].get("content"),
            }
        )
    return summaries


def usages(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for record in values:
        if record.get("kind") != "http-response":
            continue
        payload = (record.get("body") or {}).get("json")
        if not isinstance(payload, dict) or not isinstance(payload.get("usage"), dict):
            continue
        result.append(
            {
                "cost": payload.get("cost"),
                "costAvailable": payload.get("cost") is not None,
                "durationMs": record.get("durationMs"),
                "model": payload.get("model"),
                "usage": payload["usage"],
            }
        )
    return result


def database_state(target: Target, knowledge_base_id: int, session_id: str) -> dict[str, Any]:
    with target.database_connection() as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT question_gen_status, question_gen_saved_count,
                   question_gen_skipped_count, question_gen_error
            FROM knowledge_bases
            WHERE id = %s
            """,
            (knowledge_base_id,),
        )
        generation = cursor.fetchone()
        cursor.execute(
            """
            SELECT count(*), count(*) FILTER (WHERE status = 'ACTIVE')
            FROM knowledge_base_questions
            WHERE knowledge_base_id = %s
            """,
            (knowledge_base_id,),
        )
        questions = cursor.fetchone()
        cursor.execute(
            """
            SELECT source_type, knowledge_base_id, interview_category,
                   skill_id, difficulty, total_questions, status
            FROM interview_sessions
            WHERE session_id = %s
            """,
            (session_id,),
        )
        session = cursor.fetchone()
    return {
        "generationStatus": generation[0],
        "savedCount": generation[1],
        "skippedCount": generation[2],
        "error": generation[3],
        "questionCount": questions[0],
        "activeCount": questions[1],
        "session": list(session),
    }


def validate_question(question: dict[str, Any]) -> None:
    required = {
        "id",
        "knowledgeBaseId",
        "knowledgeBaseName",
        "skillId",
        "difficulty",
        "type",
        "category",
        "question",
        "topicSummary",
        "referenceAnswer",
        "keyPoints",
        "scoringRubric",
        "followUps",
        "sourceContext",
        "status",
        "createdAt",
        "updatedAt",
    }
    if set(question) != required:
        raise AssertionError(f"Unexpected question fields: {set(question)}")
    if not isinstance(question["question"], str) or not question["question"].strip():
        raise AssertionError(f"Empty generated question: {question}")
    if not isinstance(question["followUps"], list):
        raise AssertionError(f"Invalid followUps: {question}")


def capture(target: Target, knowledge_base_id: int) -> dict[str, Any]:
    before = len(records())
    with httpx.Client(base_url=target.base_url, timeout=300) as client:
        success(client.post("/api/llm-provider/reload"))
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
        completed = poll_generation(client, knowledge_base_id)
        if completed["questionGenStatus"] != "COMPLETED":
            raise AssertionError(completed)
        questions = success(
            client.get(f"/api/knowledgebase/{knowledge_base_id}/questions")
        )
        if not questions:
            raise AssertionError("Real model returned no persisted questions")
        for question in questions:
            validate_question(question)
        selectable = next(
            (
                question
                for question in questions
                if any(
                    isinstance(follow_up.get("question"), str)
                    and follow_up["question"].strip()
                    for follow_up in question["followUps"]
                )
            ),
            None,
        )
        if selectable is None:
            raise AssertionError("Real model returned no question with a usable follow-up")
        success(
            client.put(
                f"/api/knowledgebase/questions/{selectable['id']}/status",
                json={"status": "ACTIVE"},
            )
        )
        capacity = success(
            client.get(
                f"/api/knowledgebase/{knowledge_base_id}/interview-capacity",
                params={
                    "category": selectable["category"],
                    "difficulty": "mid",
                    "mainQuestionCount": 1,
                },
            )
        )
        session = success(
            client.post(
                "/api/knowledgebase-interviews/sessions",
                json={
                    "knowledgeBaseId": knowledge_base_id,
                    "category": selectable["category"],
                    "difficulty": "mid",
                    "mainQuestionCount": 1,
                    "followUpCount": 1,
                    "llmProvider": "dashscope",
                },
            )
        )
    redis_client = target.redis_connection()
    pending = redis_client.xpending(
        "knowledgebase:question-gen:stream",
        "question-gen-group",
    )
    captured_records = records()[before:]
    return {
        "queued": queued,
        "completed": completed,
        "questions": questions,
        "capacity": capacity,
        "session": session,
        "database": database_state(
            target,
            knowledge_base_id,
            session["sessionId"],
        ),
        "redis": {
            "questionStream": [
                fields
                for _, fields in redis_client.xrange(
                    "knowledgebase:question-gen:stream"
                )
            ],
            "pending": pending["pending"],
        },
        "modelRequests": request_summaries(captured_records),
        "usage": usages(captured_records),
        "provider": "dashscope",
        "capturedAt": time.time(),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "phase",
        choices=("prepare", "capture", "all"),
        nargs="?",
        default="all",
    )
    arguments = parser.parse_args()
    api_key = os.environ["AI_BAILIAN_API_KEY"]
    ids_path = REPORTS / "real-model-knowledge-base-interview-ids.json"
    if arguments.phase in {"prepare", "all"}:
        embedding = embed_context(api_key)
        ids = {
            target.name: reset_and_seed(target, embedding)
            for target in TARGETS
        }
        ids_path.write_text(
            json.dumps(ids, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if arguments.phase == "prepare":
            print("Real model knowledge-base interview data prepared")
            return
    else:
        ids = json.loads(ids_path.read_text(encoding="utf-8"))
    results = {}
    for target in TARGETS:
        results[target.name] = capture(target, int(ids[target.name]))
    java_requests = results["java"]["modelRequests"]
    python_requests = results["python"]["modelRequests"]

    def initial_requests(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
        embeddings = [
            request
            for request in values
            if request["kind"] == "embedding"
        ]
        generation = next(
            request
            for request in values
            if request["kind"] == "question-generation"
        )
        return [*embeddings, generation]

    if initial_requests(java_requests) != initial_requests(python_requests):
        raise AssertionError("Java/Python real question-generation requests differ")
    for name, value in results.items():
        embedding_count = sum(
            request["kind"] == "embedding"
            for request in value["modelRequests"]
        )
        generation_count = sum(
            request["kind"] == "question-generation"
            for request in value["modelRequests"]
        )
        if embedding_count != 4 or generation_count not in {1, 2}:
            raise AssertionError(
                f"{name} expected four embedding calls and one or two generation calls: "
                f"{value['modelRequests']}"
            )
        if not value["usage"]:
            raise AssertionError(f"{name} real model usage was not recorded")
        if value["redis"]["pending"] != 0:
            raise AssertionError(f"{name} question stream was not ACKed")
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "real-model-knowledge-base-interview.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("Real model knowledge-base interview check passed")


if __name__ == "__main__":
    main()
