#!/usr/bin/env python3
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import boto3
import httpx
import psycopg
import redis
from botocore.config import Config
from realtime_artifact import sse_record

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / "migration" / "samples" / "knowledge-base"
REPORTS = ROOT / "migration" / "reports"
STREAM_KEY = "knowledgebase:vectorize:stream"
FIXED_VECTOR = "[" + ",".join(["0"] * 1024) + "]"


@dataclass(frozen=True)
class Target:
    name: str
    base_url: str
    postgres_port: int
    redis_port: int
    database: str
    bucket: str

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

    def storage(self) -> Any:
        return boto3.client(
            "s3",
            endpoint_url="http://127.0.0.1:19000",
            aws_access_key_id="comparison-access",
            aws_secret_access_key="comparison-secret",
            region_name="us-east-1",
            config=Config(s3={"addressing_style": "path"}),
        )


TARGETS = (
    Target(
        name="java",
        base_url="http://127.0.0.1:18080",
        postgres_port=15432,
        redis_port=16379,
        database="interview_guide_java",
        bucket="interview-guide-java",
    ),
    Target(
        name="python",
        base_url="http://127.0.0.1:28080",
        postgres_port=25432,
        redis_port=26379,
        database="interview_guide_python",
        bucket="interview-guide-python",
    ),
)


def reset_target(target: Target) -> None:
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
    redis_client = target.redis_connection()
    redis_client.delete(STREAM_KEY)
    rate_limit_keys = list(redis_client.scan_iter("ratelimit:{KnowledgeBaseController:*"))
    if rate_limit_keys:
        redis_client.delete(*rate_limit_keys)
    storage = target.storage()
    response = storage.list_objects_v2(
        Bucket=target.bucket,
        Prefix="knowledgebases/",
    )
    for value in response.get("Contents", []):
        storage.delete_object(Bucket=target.bucket, Key=value["Key"])


def result(response: httpx.Response) -> dict[str, Any]:
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") != 200 or payload.get("success") is not True:
        raise AssertionError(f"Unexpected business response: {payload}")
    return payload


def upload(
    client: httpx.Client,
    path: Path,
    content_type: str,
    *,
    name: str | None,
    category: str | None,
) -> tuple[dict[str, Any], str]:
    form: dict[str, str] = {}
    if name is not None:
        form["name"] = name
    if category is not None:
        form["category"] = category
    response = client.post(
        "/api/knowledgebase/upload",
        data=form,
        files={"file": (path.name, path.read_bytes(), content_type)},
    )
    return result(response), response.text


def get_json(
    client: httpx.Client,
    path: str,
    *,
    params: dict[str, str] | None = None,
) -> dict[str, Any]:
    return result(client.get(path, params=params))


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


def database_row(target: Target, sql: str, parameters: tuple[Any, ...]) -> list[Any]:
    with target.database_connection() as connection, connection.cursor() as cursor:
        cursor.execute(sql, parameters)
        row = cursor.fetchone()
    if row is None:
        raise AssertionError(f"Expected database row for {target.name}: {sql}")
    return list(row)


def seed_delete_graph(target: Target, knowledge_base_id: int) -> None:
    with target.database_connection() as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO rag_chat_sessions (
                created_at,
                is_pinned,
                message_count,
                status,
                title,
                updated_at
            )
            VALUES (
                TIMESTAMP '2026-08-16 08:00:00',
                false,
                0,
                'ACTIVE',
                'knowledge-base-comparison-delete',
                TIMESTAMP '2026-08-16 08:00:00'
            )
            RETURNING id
            """
        )
        session_id = cursor.fetchone()[0]
        cursor.execute(
            """
            INSERT INTO rag_session_knowledge_bases (session_id, knowledge_base_id)
            VALUES (%s, %s)
            """,
            (session_id, knowledge_base_id),
        )
        cursor.execute(
            """
            INSERT INTO vector_store (content, metadata, embedding)
            VALUES
                ('formal comparison vector', %s::json, %s::vector),
                ('legacy comparison vector', %s::json, %s::vector)
            """,
            (
                json.dumps({"kb_id": str(knowledge_base_id)}),
                FIXED_VECTOR,
                json.dumps({"kb_id_long": str(knowledge_base_id)}),
                FIXED_VECTOR,
            ),
        )


def object_exists(target: Target, key: str) -> bool:
    try:
        target.storage().head_object(Bucket=target.bucket, Key=key)
    except Exception:
        return False
    return True


def normalize(value: Any, target: Target) -> Any:
    if isinstance(value, dict):
        return {key: normalize(item, target) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize(item, target) for item in value]
    if isinstance(value, str):
        return value.replace(target.bucket, "{{BUCKET}}")
    return value


def capture_target(target: Target) -> dict[str, Any]:
    text_sample = SAMPLES / "fixed-knowledge-base.txt"
    markdown_sample = SAMPLES / "fixed-knowledge-base.md"
    with httpx.Client(base_url=target.base_url, timeout=30) as client:
        first, first_raw = upload(
            client,
            text_sample,
            "text/plain",
            name="固定 TXT 样本",
            category="基础",
        )
        first_data = first["data"]
        first_id = int(first_data["knowledgeBase"]["id"])
        first_key = str(first_data["storage"]["fileKey"])

        duplicate, duplicate_raw = upload(
            client,
            text_sample,
            "text/plain",
            name="重复名称不会生效",
            category="重复分类不会生效",
        )
        second, second_raw = upload(
            client,
            markdown_sample,
            "text/markdown",
            name="固定 Markdown 样本",
            category=None,
        )
        second_data = second["data"]
        second_id = int(second_data["knowledgeBase"]["id"])
        second_key = str(second_data["storage"]["fileKey"])

        initial_reads = {
            "list": get_json(client, "/api/knowledgebase/list"),
            "detail": get_json(client, f"/api/knowledgebase/{first_id}"),
            "categories": get_json(client, "/api/knowledgebase/categories"),
            "category": get_json(client, "/api/knowledgebase/category/基础"),
            "uncategorized": get_json(client, "/api/knowledgebase/uncategorized"),
            "searchName": get_json(
                client,
                "/api/knowledgebase/search",
                params={"keyword": "Markdown"},
            ),
            "searchCategoryOnly": get_json(
                client,
                "/api/knowledgebase/search",
                params={"keyword": "基础"},
            ),
            "statistics": get_json(client, "/api/knowledgebase/stats"),
        }

        update_category = result(
            client.put(
                f"/api/knowledgebase/{second_id}/category",
                json={"category": "文档"},
            )
        )
        category_reads = {
            "update": update_category,
            "categories": get_json(client, "/api/knowledgebase/categories"),
            "category": get_json(client, "/api/knowledgebase/category/文档"),
        }

        download = client.get(f"/api/knowledgebase/{first_id}/download")
        download.raise_for_status()
        download_state = {
            "body": download.content.decode("utf-8"),
            "contentDisposition": download.headers.get("content-disposition"),
            "contentLength": download.headers.get("content-length"),
            "contentType": download.headers.get("content-type"),
        }

        redis_client = target.redis_connection()
        redis_client.delete(STREAM_KEY)
        revectorize = result(client.post(f"/api/knowledgebase/{first_id}/revectorize"))
        stream_messages = redis_client.xrange(STREAM_KEY)
        revectorize_database = database_row(
            target,
            """
            SELECT vector_status, vector_error
            FROM knowledge_bases
            WHERE id = %s
            """,
            (first_id,),
        )
        revectorize_state = {
            "response": revectorize,
            "database": revectorize_database,
            "stream": [fields for _, fields in stream_messages],
        }

        empty_ids_query = client.post(
            "/api/knowledgebase/query",
            json={"knowledgeBaseIds": [], "question": "固定问题"},
        )
        blank_question_query = client.post(
            "/api/knowledgebase/query",
            json={"knowledgeBaseIds": [first_id], "question": " \t"},
        )
        missing_ids_query = client.post(
            "/api/knowledgebase/query",
            json={"question": "固定问题"},
        )
        missing_question_query = client.post(
            "/api/knowledgebase/query",
            json={"knowledgeBaseIds": [first_id]},
        )
        empty_ids_stream = client.post(
            "/api/knowledgebase/query/stream",
            json={"knowledgeBaseIds": [], "question": "固定问题"},
        )
        null_id_sync = client.post(
            "/api/knowledgebase/query",
            json={"knowledgeBaseIds": [None], "question": "固定问题"},
        )
        null_id_stream = client.post(
            "/api/knowledgebase/query/stream",
            json={"knowledgeBaseIds": [None], "question": "固定问题"},
        )
        missing_id = 9223372036854775807
        missing_sync = client.post(
            "/api/knowledgebase/query",
            json={"knowledgeBaseIds": [missing_id], "question": "固定问题"},
        )
        missing_stream = client.post(
            "/api/knowledgebase/query/stream",
            json={"knowledgeBaseIds": [missing_id], "question": "固定问题"},
        )
        non_model_query_state = {
            "validation": {
                "emptyIdsSync": {
                    "body": empty_ids_query.json(),
                    "contentType": empty_ids_query.headers.get("content-type"),
                    "status": empty_ids_query.status_code,
                },
                "blankQuestionSync": {
                    "body": blank_question_query.json(),
                    "contentType": blank_question_query.headers.get("content-type"),
                    "status": blank_question_query.status_code,
                },
                "missingIdsSync": {
                    "body": missing_ids_query.json(),
                    "contentType": missing_ids_query.headers.get("content-type"),
                    "status": missing_ids_query.status_code,
                },
                "missingQuestionSync": {
                    "body": missing_question_query.json(),
                    "contentType": missing_question_query.headers.get("content-type"),
                    "status": missing_question_query.status_code,
                },
                "emptyIdsStream": {
                    "body": empty_ids_stream.json(),
                    "contentType": empty_ids_stream.headers.get("content-type"),
                    "status": empty_ids_stream.status_code,
                },
            },
            "nullKnowledgeBaseId": {
                "sync": {
                    "body": null_id_sync.json(),
                    "contentType": null_id_sync.headers.get("content-type"),
                    "status": null_id_sync.status_code,
                },
                "stream": sse_record(
                    null_id_stream.content,
                    null_id_stream.status_code,
                    tracked_sse_headers(null_id_stream),
                ),
            },
            "missingKnowledgeBase": {
                "sync": {
                    "body": missing_sync.json(),
                    "contentType": missing_sync.headers.get("content-type"),
                    "status": missing_sync.status_code,
                },
                "stream": sse_record(
                    missing_stream.content,
                    missing_stream.status_code,
                    tracked_sse_headers(missing_stream),
                ),
            },
            "database": {
                "firstQuestionCount": database_row(
                    target,
                    "SELECT question_count FROM knowledge_bases WHERE id = %s",
                    (first_id,),
                )[0],
                "ragMessageCount": database_row(
                    target,
                    "SELECT count(*) FROM rag_chat_messages",
                    (),
                )[0],
            },
        }

        seed_delete_graph(target, second_id)
        delete_preconditions = {
            "objectExists": object_exists(target, second_key),
            "associationCount": database_row(
                target,
                """
                SELECT count(*)
                FROM rag_session_knowledge_bases
                WHERE knowledge_base_id = %s
                """,
                (second_id,),
            )[0],
            "vectorCount": database_row(
                target,
                """
                SELECT count(*)
                FROM vector_store
                WHERE metadata->>'kb_id' = %s
                   OR metadata->>'kb_id_long' = %s
                """,
                (str(second_id), str(second_id)),
            )[0],
        }
        deleted = result(client.delete(f"/api/knowledgebase/{second_id}"))
        delete_state = {
            "response": deleted,
            "knowledgeBaseCount": database_row(
                target,
                "SELECT count(*) FROM knowledge_bases WHERE id = %s",
                (second_id,),
            )[0],
            "associationCount": database_row(
                target,
                """
                SELECT count(*)
                FROM rag_session_knowledge_bases
                WHERE knowledge_base_id = %s
                """,
                (second_id,),
            )[0],
            "vectorCount": database_row(
                target,
                """
                SELECT count(*)
                FROM vector_store
                WHERE metadata->>'kb_id' = %s
                   OR metadata->>'kb_id_long' = %s
                """,
                (str(second_id), str(second_id)),
            )[0],
            "objectExists": object_exists(target, second_key),
        }

    return {
        "firstUpload": first,
        "duplicateUpload": duplicate,
        "markdownUpload": second,
        "rawMapOfResponses": {
            "firstUpload": first_raw,
            "duplicateUpload": duplicate_raw,
            "markdownUpload": second_raw,
        },
        "initialReads": initial_reads,
        "categoryReads": category_reads,
        "download": download_state,
        "revectorize": revectorize_state,
        "nonModelQuery": non_model_query_state,
        "deletePreconditions": delete_preconditions,
        "delete": delete_state,
        "objectKeys": {
            "first": first_key,
            "second": second_key,
        },
    }


def main() -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    for target in TARGETS:
        reset_target(target)
    captures = {target.name: capture_target(target) for target in TARGETS}
    normalized = {target.name: normalize(captures[target.name], target) for target in TARGETS}
    left = dict(normalized["java"])
    right = dict(normalized["python"])
    left.pop("rawMapOfResponses")
    right.pop("rawMapOfResponses")
    report = {
        "schemaVersion": 1,
        "fakeEmbedding": False,
        "fakeModel": False,
        "realEmbeddingValidated": False,
        "realModelValidated": False,
        "knownVariants": ["knowledge-base-upload-map-field-order"],
        "passed": left == right,
        "java": captures["java"],
        "python": captures["python"],
        "normalizedJava": left,
        "normalizedPython": right,
    }
    output = REPORTS / "knowledge-base-comparison.json"
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if not report["passed"]:
        raise SystemExit(f"Knowledge base comparison failed: {output}")
    print(f"Knowledge base comparison passed: {output}")


if __name__ == "__main__":
    main()
