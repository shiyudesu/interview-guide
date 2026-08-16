"""Create the schema matching the final Flyway state.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-08-16
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path

from alembic import op

revision: str = "0001_initial_schema"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = (
    "voice_interview_messages",
    "voice_interview_evaluations",
    "voice_interview_sessions",
    "rag_session_knowledge_bases",
    "rag_chat_messages",
    "rag_chat_sessions",
    "knowledge_base_questions",
    "vector_store",
    "interview_answers",
    "interview_sessions",
    "resume_analyses",
    "knowledge_bases",
    "resumes",
    "llm_global_setting",
    "llm_provider_config",
    "interview_schedule",
)


def has_sql_content(statement: str) -> bool:
    without_block_comments = re.sub(r"/\*.*?\*/", "", statement, flags=re.DOTALL)
    without_comments = re.sub(
        r"(?m)^\s*--.*$",
        "",
        without_block_comments,
    )
    return bool(without_comments.strip())


def split_sql_statements(document: str) -> list[str]:
    statements: list[str] = []
    start = 0
    index = 0
    single_quote = False
    double_quote = False
    line_comment = False
    block_comment = False
    dollar_tag: str | None = None
    while index < len(document):
        if line_comment:
            if document[index] == "\n":
                line_comment = False
            index += 1
            continue
        if block_comment:
            if document.startswith("*/", index):
                block_comment = False
                index += 2
            else:
                index += 1
            continue
        if dollar_tag is not None:
            if document.startswith(dollar_tag, index):
                index += len(dollar_tag)
                dollar_tag = None
            else:
                index += 1
            continue
        if single_quote:
            if document.startswith("''", index):
                index += 2
            elif document[index] == "'":
                single_quote = False
                index += 1
            else:
                index += 1
            continue
        if double_quote:
            if document.startswith('""', index):
                index += 2
            elif document[index] == '"':
                double_quote = False
                index += 1
            else:
                index += 1
            continue
        if document.startswith("--", index):
            line_comment = True
            index += 2
            continue
        if document.startswith("/*", index):
            block_comment = True
            index += 2
            continue
        character = document[index]
        if character == "'":
            single_quote = True
            index += 1
            continue
        if character == '"':
            double_quote = True
            index += 1
            continue
        if character == "$":
            tag_match = re.match(r"\$[A-Za-z_0-9]*\$", document[index:])
            if tag_match:
                dollar_tag = tag_match.group(0)
                index += len(dollar_tag)
                continue
        if character == ";":
            statement = document[start:index].strip()
            if statement and has_sql_content(statement):
                statements.append(statement)
            start = index + 1
        index += 1
    trailing = document[start:].strip()
    if trailing and has_sql_content(trailing):
        statements.append(trailing)
    if single_quote or double_quote or block_comment or dollar_tag is not None:
        raise ValueError("Unterminated SQL construct in initial schema")
    return statements


def upgrade() -> None:
    sql_path = Path(__file__).resolve().parents[1] / "sql/0001_initial_schema.sql"
    document = sql_path.read_text(encoding="utf-8")
    connection = op.get_bind()
    for statement in split_sql_statements(document):
        connection.exec_driver_sql(statement)


def downgrade() -> None:
    for table in TABLES:
        op.execute(f'DROP TABLE IF EXISTS "{table}" CASCADE')
    op.execute('DROP EXTENSION IF EXISTS "vector"')
    op.execute('DROP EXTENSION IF EXISTS "uuid-ossp"')
    op.execute('DROP EXTENSION IF EXISTS "hstore"')
