#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import psycopg
import redis
from model_record_reader import read_jsonl_records
from realtime_artifact import sse_record

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "migration" / "reports"
MODEL_RECORDS = REPORTS / "model-proxy.jsonl"
QUESTION = "知识库向量维度是多少？"
CONTEXT = "本系统知识库使用固定的 1024 维向量，并使用余弦相似度执行检索。"
NO_RESULT_RESPONSE = (
    "抱歉，在选定的知识库中未检索到相关信息。请换一个更具体的关键词或补充上下文后再试。"
)
MODEL_PROXY_CONTROL = "http://127.0.0.1:18090/__control"
EMBEDDING_MODEL = os.getenv("AI_EMBEDDING_MODEL", "qwen3.7-text-embedding")
FAULT_INJECTION_COUNT = 10


@dataclass(frozen=True)
class Target:
    name: str
    base_url: str
    postgres_port: int
    redis_port: int
    database: str

    def database_connection(self) -> psycopg.Connection[Any]:
        return psycopg.connect(
            host="127.0.0.1",
            port=self.postgres_port,
            dbname=self.database,
            user="postgres",
            password="comparison-password",
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


def model_records() -> list[dict[str, Any]]:
    return read_jsonl_records(MODEL_RECORDS)


def embed_question(api_key: str) -> list[float]:
    response = httpx.post(
        ("http://127.0.0.1:18090/proxy/https/dashscope.aliyuncs.com/compatible-mode/v1/embeddings"),
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": EMBEDDING_MODEL,
            "input": [QUESTION],
            "dimensions": 1024,
        },
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()
    embedding = payload["data"][0]["embedding"]
    values = [float(value) for value in embedding]
    if len(values) != 1024:
        raise AssertionError(f"Expected 1024 embedding dimensions, got {len(values)}")
    return values


def reset_and_seed(target: Target, embedding: list[float]) -> int:
    with target.database_connection() as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            TRUNCATE TABLE
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
                access_count,
                chunk_count,
                content_type,
                file_hash,
                file_size,
                name,
                original_filename,
                question_count,
                uploaded_at,
                vector_status
            )
            VALUES (
                1,
                1,
                'text/plain',
                %s,
                %s,
                '真实模型知识库',
                'real-model-knowledge-base.txt',
                0,
                TIMESTAMP '2026-08-16 08:00:00',
                'COMPLETED'
            )
            RETURNING id
            """,
            (
                hashlib.sha256(CONTEXT.encode()).hexdigest(),
                len(CONTEXT.encode()),
            ),
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
    redis_client = target.redis_connection()
    keys = list(redis_client.scan_iter("ratelimit:{KnowledgeBaseController:*"))
    if keys:
        redis_client.delete(*keys)
    return knowledge_base_id


def result_payload(response: httpx.Response) -> dict[str, Any]:
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data")
    if payload.get("code") != 200 or payload.get("success") is not True:
        raise AssertionError(f"Real knowledge-base query failed: {payload}")
    if not isinstance(data, dict):
        raise AssertionError(f"Missing knowledge-base response data: {payload}")
    answer = data.get("answer")
    if not isinstance(answer, str) or not answer.strip():
        raise AssertionError(f"Knowledge-base answer is empty: {payload}")
    if answer == NO_RESULT_RESPONSE or answer.startswith("【错误】"):
        raise AssertionError(f"Knowledge-base answer did not use the seeded hit: {payload}")
    return payload


def success_data(response: httpx.Response) -> Any:
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") != 200 or payload.get("success") is not True:
        raise AssertionError(f"Unexpected business response: {payload}")
    return payload.get("data")


def configure_fault(count: int) -> None:
    response = httpx.post(
        f"{MODEL_PROXY_CONTROL}/fault",
        json={"count": count, "mode": "status", "status": 503},
        timeout=10,
    )
    response.raise_for_status()


def reset_fault() -> None:
    response = httpx.post(f"{MODEL_PROXY_CONTROL}/reset", timeout=10)
    response.raise_for_status()


def tracked_sse_headers(response: httpx.Response) -> dict[str, str]:
    return {
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


def request_summaries(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for record in records:
        if record.get("kind") != "http-request":
            continue
        body = record.get("body") or {}
        payload = body.get("json")
        if not isinstance(payload, dict):
            continue
        upstream = str(record.get("upstream", ""))
        if not upstream.endswith(("/chat/completions", "/embeddings")):
            continue
        messages = payload.get("messages")
        tools = payload.get("tools")
        summaries.append(
            {
                "endpoint": upstream.rsplit("/", 1)[-1],
                "model": payload.get("model"),
                "stream": payload.get("stream", False),
                "temperature": payload.get("temperature"),
                "dimensions": payload.get("dimensions"),
                "encodingFormat": payload.get("encoding_format"),
                "inputCount": (
                    len(payload.get("input", []))
                    if isinstance(payload.get("input"), list)
                    else None
                ),
                "roles": (
                    [message.get("role") for message in messages]
                    if isinstance(messages, list)
                    else None
                ),
                "toolNames": (
                    [
                        tool.get("function", {}).get("name")
                        for tool in tools
                        if isinstance(tool, dict)
                    ]
                    if isinstance(tools, list)
                    else []
                ),
            }
        )
    return summaries


def rag_message_state(
    target: Target,
    session_id: int,
) -> list[dict[str, Any]]:
    with target.database_connection() as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT type, content, message_order, completed
            FROM rag_chat_messages
            WHERE session_id = %s
            ORDER BY message_order
            """,
            (session_id,),
        )
        return [
            {
                "type": message_type,
                "content": content,
                "messageOrder": message_order,
                "completed": completed,
            }
            for message_type, content, message_order, completed in cursor.fetchall()
        ]


def rag_stream_text(record: dict[str, Any]) -> str:
    return "".join(
        str(frame["data"]).replace("\\n", "\n").replace("\\r", "\r") for frame in record["frames"]
    )


def capture_target(target: Target, knowledge_base_id: int) -> dict[str, Any]:
    before = len(model_records())
    request = {
        "knowledgeBaseIds": [knowledge_base_id],
        "question": QUESTION,
    }
    with httpx.Client(base_url=target.base_url, timeout=180) as client:
        sync = result_payload(client.post("/api/knowledgebase/query", json=request))
        stream_response = client.post(
            "/api/knowledgebase/query/stream",
            json=request,
        )
        with client.stream(
            "POST",
            "/api/knowledgebase/query/stream",
            json=request,
        ) as cancelled_response:
            cancelled_body = bytearray()
            for chunk in cancelled_response.iter_raw():
                cancelled_body.extend(chunk)
                break
            cancelled_stream = sse_record(
                bytes(cancelled_body),
                cancelled_response.status_code,
                {
                    key.lower(): value
                    for key, value in cancelled_response.headers.items()
                    if key.lower()
                    in {
                        "content-type",
                        "cache-control",
                        "connection",
                        "x-accel-buffering",
                    }
                },
                cancelled=True,
                completed=False,
            )
        rag_session = success_data(
            client.post(
                "/api/rag-chat/sessions",
                json={
                    "knowledgeBaseIds": [knowledge_base_id],
                    "title": "真实模型 RAG Chat",
                },
            )
        )
        if not isinstance(rag_session, dict):
            raise AssertionError(f"Missing RAG Chat session: {rag_session}")
        rag_session_id = int(rag_session["id"])
        rag_normal_response = client.post(
            f"/api/rag-chat/sessions/{rag_session_id}/messages/stream",
            json={"question": QUESTION},
        )
        rag_normal = sse_record(
            rag_normal_response.content,
            rag_normal_response.status_code,
            tracked_sse_headers(rag_normal_response),
        )
        rag_normal_text = rag_stream_text(rag_normal)
        normal_records = model_records()[before:]

        configure_fault(FAULT_INJECTION_COUNT)
        try:
            rag_error_response = client.post(
                f"/api/rag-chat/sessions/{rag_session_id}/messages/stream",
                json={"question": "请再次说明向量维度"},
            )
        finally:
            reset_fault()
        rag_error = sse_record(
            rag_error_response.content,
            rag_error_response.status_code,
            tracked_sse_headers(rag_error_response),
        )
        rag_error_text = rag_stream_text(rag_error)
    stream = sse_record(
        stream_response.content,
        stream_response.status_code,
        {
            key.lower(): value
            for key, value in stream_response.headers.items()
            if key.lower()
            in {
                "content-type",
                "cache-control",
                "connection",
                "x-accel-buffering",
            }
        },
    )
    stream_text = "".join(frame["data"] for frame in stream["frames"])
    if (
        stream_response.status_code != 200
        or not stream_text.strip()
        or stream_text == NO_RESULT_RESPONSE
        or "【错误】" in stream_text
    ):
        raise AssertionError(f"Real knowledge-base stream failed for {target.name}: {stream}")
    with target.database_connection() as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT question_count
            FROM knowledge_bases
            WHERE id = %s
            """,
            (knowledge_base_id,),
        )
        question_count = int(cursor.fetchone()[0])
        cursor.execute("SELECT count(*) FROM rag_chat_messages")
        rag_message_count = int(cursor.fetchone()[0])
    rag_messages = rag_message_state(target, rag_session_id)
    if (
        not rag_normal_text.strip()
        or rag_normal_text == NO_RESULT_RESPONSE
        or "【错误】" in rag_normal_text
    ):
        raise AssertionError(f"Real RAG Chat stream failed for {target.name}: {rag_normal}")
    if not rag_error_text.startswith("【错误】"):
        raise AssertionError(f"RAG Chat fault was not recorded for {target.name}: {rag_error}")
    if len(rag_messages) != 4:
        raise AssertionError(f"Unexpected RAG Chat message state: {rag_messages}")
    if (
        rag_messages[1]["content"] != rag_normal_text
        or rag_messages[1]["completed"] is not True
        or rag_messages[3]["content"] != rag_error_text
        or rag_messages[3]["completed"] is not True
    ):
        raise AssertionError(f"RAG Chat persistence mismatch: {rag_messages}")
    return {
        "sync": sync,
        "stream": stream,
        "cancelledStream": cancelled_stream,
        "streamText": stream_text,
        "questionCount": question_count,
        "ragMessageCount": rag_message_count,
        "requests": request_summaries(normal_records),
        "ragChat": {
            "faultInjectionCount": FAULT_INJECTION_COUNT,
            "session": rag_session,
            "normal": rag_normal,
            "normalText": rag_normal_text,
            "error": rag_error,
            "errorText": rag_error_text,
            "messages": rag_messages,
        },
    }


def main() -> None:
    api_key = os.environ.get("AI_BAILIAN_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("AI_BAILIAN_API_KEY is required")
    embedding = embed_question(api_key)
    knowledge_base_ids = {target.name: reset_and_seed(target, embedding) for target in TARGETS}
    captures = {
        target.name: capture_target(target, knowledge_base_ids[target.name]) for target in TARGETS
    }
    java_requests = captures["java"]["requests"]
    python_requests = captures["python"]["requests"]
    request_shape_passed = java_requests == python_requests
    functional_passed = all(
        capture["questionCount"] == 5
        and capture["ragMessageCount"] == 4
        and capture["cancelledStream"]["cancelled"] is True
        and capture["cancelledStream"]["completed"] is False
        and capture["ragChat"]["normal"]["completed"] is True
        and capture["ragChat"]["error"]["completed"] is True
        for capture in captures.values()
    )
    report = {
        "schemaVersion": 1,
        "provider": "dashscope",
        "embeddingModel": EMBEDDING_MODEL,
        "embeddingDimensions": len(embedding),
        "question": QUESTION,
        "fakeModel": False,
        "realEmbeddingValidated": len(embedding) == 1024,
        "realModelValidated": functional_passed and request_shape_passed,
        "requestShapePassed": request_shape_passed,
        "functionalPassed": functional_passed,
        **captures,
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    output = REPORTS / "real-model-knowledge-base.json"
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if not report["realModelValidated"]:
        raise SystemExit(f"Real knowledge-base model comparison failed: {output}")
    print(f"Real knowledge-base model comparison passed: {output}")


if __name__ == "__main__":
    main()
