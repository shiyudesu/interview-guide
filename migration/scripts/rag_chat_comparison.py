#!/usr/bin/env python3
from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import psycopg
from realtime_artifact import sse_record

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "migration" / "reports"
MISSING_ID = 9223372036854775807


@dataclass(frozen=True)
class Target:
    name: str
    base_url: str
    postgres_port: int
    database: str

    def database_connection(self) -> psycopg.Connection[Any]:
        return psycopg.connect(
            host="127.0.0.1",
            port=self.postgres_port,
            dbname=self.database,
            user="postgres",
            password="comparison-password",
        )


TARGETS = (
    Target("java", "http://127.0.0.1:18080", 15432, "interview_guide_java"),
    Target("python", "http://127.0.0.1:28080", 25432, "interview_guide_python"),
)


def reset_and_seed(target: Target) -> tuple[int, int]:
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
                last_accessed_at,
                name,
                original_filename,
                question_count,
                question_gen_status,
                uploaded_at,
                vector_status
            )
            VALUES
                (
                    1,
                    0,
                    'text/plain',
                    repeat('1', 64),
                    10,
                    TIMESTAMP '2026-08-16 08:00:00',
                    '固定知识库一',
                    'fixed-one.txt',
                    0,
                    'NONE',
                    TIMESTAMP '2026-08-16 08:00:00',
                    'COMPLETED'
                ),
                (
                    2,
                    3,
                    'text/markdown',
                    repeat('2', 64),
                    20,
                    TIMESTAMP '2026-08-16 08:00:00',
                    '固定知识库二',
                    'fixed-two.md',
                    4,
                    'NONE',
                    TIMESTAMP '2026-08-16 08:00:00',
                    'COMPLETED'
                )
            RETURNING id
            """
        )
        ids = [int(row[0]) for row in cursor.fetchall()]
    return ids[0], ids[1]


def response_record(response: httpx.Response) -> dict[str, Any]:
    try:
        body: Any = response.json()
    except ValueError:
        body = response.text
    return {
        "status": response.status_code,
        "contentType": response.headers.get("content-type"),
        "body": body,
        "rawBody": response.text,
    }


def tracked_sse_headers(response: httpx.Response) -> dict[str, str]:
    return {
        key.lower(): value
        for key, value in response.headers.items()
        if key.lower()
        in {
            "content-type",
            "cache-control",
            "x-accel-buffering",
        }
    }


def normalize_database_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [normalize_database_value(item) for item in value]
    if isinstance(value, tuple):
        return [normalize_database_value(item) for item in value]
    return value


def database_state(target: Target, session_id: int) -> dict[str, Any]:
    with target.database_connection() as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                id,
                title,
                status,
                message_count,
                is_pinned,
                created_at,
                updated_at
            FROM rag_chat_sessions
            WHERE id = %s
            """,
            (session_id,),
        )
        session = cursor.fetchone()
        cursor.execute(
            """
            SELECT knowledge_base_id
            FROM rag_session_knowledge_bases
            WHERE session_id = %s
            ORDER BY knowledge_base_id
            """,
            (session_id,),
        )
        knowledge_base_ids = [int(row[0]) for row in cursor.fetchall()]
        cursor.execute(
            """
            SELECT
                id,
                type,
                content,
                message_order,
                completed,
                created_at,
                updated_at
            FROM rag_chat_messages
            WHERE session_id = %s
            ORDER BY message_order
            """,
            (session_id,),
        )
        messages = cursor.fetchall()
    return {
        "session": normalize_database_value(session),
        "knowledgeBaseIds": knowledge_base_ids,
        "messages": normalize_database_value(messages),
    }


def set_updated_times(
    target: Target,
    older_session_id: int,
    newer_session_id: int,
) -> None:
    with target.database_connection() as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE rag_chat_sessions
            SET updated_at = CASE id
                WHEN %s THEN TIMESTAMP '2026-08-16 07:00:00'
                WHEN %s THEN TIMESTAMP '2026-08-16 09:00:00'
            END
            WHERE id IN (%s, %s)
            """,
            (
                older_session_id,
                newer_session_id,
                older_session_id,
                newer_session_id,
            ),
        )


def capture_target(target: Target, first_id: int, second_id: int) -> dict[str, Any]:
    with httpx.Client(base_url=target.base_url, timeout=30) as client:
        validation = {
            "emptyCreate": response_record(
                client.post(
                    "/api/rag-chat/sessions",
                    json={"knowledgeBaseIds": [], "title": None},
                )
            ),
            "missingCreate": response_record(
                client.post(
                    "/api/rag-chat/sessions",
                    json={"knowledgeBaseIds": [MISSING_ID], "title": None},
                )
            ),
            "duplicateCreate": response_record(
                client.post(
                    "/api/rag-chat/sessions",
                    json={"knowledgeBaseIds": [first_id, first_id], "title": None},
                )
            ),
            "blankTitle": response_record(
                client.put(
                    f"/api/rag-chat/sessions/{MISSING_ID}/title",
                    json={"title": " \t"},
                )
            ),
            "emptyKnowledgeBases": response_record(
                client.put(
                    f"/api/rag-chat/sessions/{MISSING_ID}/knowledge-bases",
                    json={"knowledgeBaseIds": []},
                )
            ),
        }
        create_response = client.post(
            "/api/rag-chat/sessions",
            json={"knowledgeBaseIds": [first_id], "title": None},
        )
        created = response_record(create_response)
        session_id = int(create_response.json()["data"]["id"])
        secondary_response = client.post(
            "/api/rag-chat/sessions",
            json={
                "knowledgeBaseIds": [first_id, second_id],
                "title": "次要固定会话",
            },
        )
        created_secondary = response_record(secondary_response)
        secondary_session_id = int(secondary_response.json()["data"]["id"])
        set_updated_times(target, session_id, secondary_session_id)
        initial = {
            "list": response_record(client.get("/api/rag-chat/sessions")),
            "detail": response_record(client.get(f"/api/rag-chat/sessions/{session_id}")),
        }
        mutations = {
            "title": response_record(
                client.put(
                    f"/api/rag-chat/sessions/{session_id}/title",
                    json={"title": "  固定会话标题  "},
                )
            ),
            "pin": response_record(client.put(f"/api/rag-chat/sessions/{session_id}/pin")),
            "knowledgeBases": response_record(
                client.put(
                    f"/api/rag-chat/sessions/{session_id}/knowledge-bases",
                    json={"knowledgeBaseIds": [second_id, MISSING_ID]},
                )
            ),
        }
        after_mutation = {
            "list": response_record(client.get("/api/rag-chat/sessions")),
            "detail": response_record(client.get(f"/api/rag-chat/sessions/{session_id}")),
        }
        stream_errors = {
            "blankQuestion": response_record(
                client.post(
                    f"/api/rag-chat/sessions/{session_id}/messages/stream",
                    json={"question": " \t"},
                )
            ),
            "missingSession": response_record(
                client.post(
                    f"/api/rag-chat/sessions/{MISSING_ID}/messages/stream",
                    json={"question": "固定问题"},
                )
            ),
        }
        clear_associations = response_record(
            client.put(
                f"/api/rag-chat/sessions/{session_id}/knowledge-bases",
                json={"knowledgeBaseIds": [MISSING_ID]},
            )
        )
        no_model_stream_response = client.post(
            f"/api/rag-chat/sessions/{session_id}/messages/stream",
            json={"question": "固定无模型问题"},
        )
        no_model_stream = sse_record(
            no_model_stream_response.content,
            no_model_stream_response.status_code,
            tracked_sse_headers(no_model_stream_response),
        )
        after_stream = response_record(client.get(f"/api/rag-chat/sessions/{session_id}"))
        state = database_state(target, session_id)
        deleted = response_record(client.delete(f"/api/rag-chat/sessions/{session_id}"))
        deleted_secondary = response_record(
            client.delete(f"/api/rag-chat/sessions/{secondary_session_id}")
        )
        after_delete = {
            "detail": response_record(client.get(f"/api/rag-chat/sessions/{session_id}")),
            "deleteAgain": response_record(client.delete(f"/api/rag-chat/sessions/{session_id}")),
        }
    return {
        "validation": validation,
        "created": created,
        "createdSecondary": created_secondary,
        "initial": initial,
        "mutations": mutations,
        "afterMutation": after_mutation,
        "streamErrors": stream_errors,
        "clearAssociations": clear_associations,
        "noModelStream": no_model_stream,
        "afterStream": after_stream,
        "database": state,
        "deleted": deleted,
        "deletedSecondary": deleted_secondary,
        "afterDelete": after_delete,
    }


def normalize_known_set_order(value: Any, key: str | None = None) -> Any:
    if isinstance(value, dict):
        normalized = {
            item_key: normalize_known_set_order(item, item_key) for item_key, item in value.items()
        }
        if "body" in normalized and "rawBody" in normalized:
            normalized["rawBody"] = json.dumps(
                normalized["body"],
                ensure_ascii=False,
                separators=(",", ":"),
            )
        return normalized
    if isinstance(value, list):
        normalized_items = [normalize_known_set_order(item) for item in value]
        if key in {"knowledgeBaseIds", "knowledgeBaseNames"}:
            return sorted(normalized_items)
        if key == "knowledgeBases":
            return sorted(
                normalized_items,
                key=lambda item: item.get("id", 0) if isinstance(item, dict) else 0,
            )
        return normalized_items
    return value


def main() -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    captures: dict[str, dict[str, Any]] = {}
    for target in TARGETS:
        first_id, second_id = reset_and_seed(target)
        captures[target.name] = capture_target(target, first_id, second_id)
    normalized = {
        name: normalize_known_set_order(deepcopy(capture)) for name, capture in captures.items()
    }
    report = {
        "schemaVersion": 1,
        "fakeModel": False,
        "realModelValidated": False,
        "scope": "RAG Chat CRUD, validation, no-model SSE, and persisted messages",
        "knownVariants": ["rag-chat-knowledge-base-hash-set-order"],
        "passed": normalized["java"] == normalized["python"],
        "normalizedJava": normalized["java"],
        "normalizedPython": normalized["python"],
        **captures,
    }
    output = REPORTS / "rag-chat-comparison.json"
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if not report["passed"]:
        raise SystemExit(f"RAG Chat comparison failed: {output}")
    print(f"RAG Chat comparison passed: {output}")


if __name__ == "__main__":
    main()
