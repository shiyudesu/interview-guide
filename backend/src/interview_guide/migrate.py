from __future__ import annotations

import os
from pathlib import Path

import psycopg
from alembic.config import Config

from alembic import command
from interview_guide.common.config.settings import get_settings

EXPECTED_FLYWAY_VERSIONS = frozenset(
    {
        "1",
        "20260722",
        "20260723",
        "20260724",
        "20260803",
    }
)
EXPECTED_BUSINESS_TABLES = frozenset(
    {
        "interview_answers",
        "interview_schedule",
        "interview_sessions",
        "knowledge_base_questions",
        "knowledge_bases",
        "llm_global_setting",
        "llm_provider_config",
        "rag_chat_messages",
        "rag_chat_sessions",
        "rag_session_knowledge_bases",
        "resume_analyses",
        "resumes",
        "vector_store",
        "voice_interview_evaluations",
        "voice_interview_messages",
        "voice_interview_sessions",
    }
)
BASELINE_ENV = "APP_MIGRATION_BASELINE_FLYWAY"


def should_stamp_flyway_schema(
    *,
    alembic_exists: bool,
    flyway_exists: bool,
    flyway_versions: frozenset[str],
    business_tables: frozenset[str],
    baseline_enabled: bool,
) -> bool:
    if alembic_exists or not flyway_exists:
        return False
    if not baseline_enabled:
        raise RuntimeError(
            "Flyway schema detected without Alembic history; set "
            f"{BASELINE_ENV}=true only after Java/Python schema acceptance"
        )
    if flyway_versions != EXPECTED_FLYWAY_VERSIONS:
        raise RuntimeError(
            "Flyway history does not match the accepted Java baseline: "
            f"expected={sorted(EXPECTED_FLYWAY_VERSIONS)}, "
            f"actual={sorted(flyway_versions)}"
        )
    missing_tables = EXPECTED_BUSINESS_TABLES - business_tables
    if missing_tables:
        raise RuntimeError(
            "Flyway schema is missing required business tables: "
            + ", ".join(sorted(missing_tables))
        )
    return True


def inspect_existing_schema() -> tuple[bool, bool, frozenset[str], frozenset[str]]:
    settings = get_settings()
    with (
        psycopg.connect(
            host=settings.postgres_host,
            port=settings.postgres_port,
            dbname=settings.postgres_db,
            user=settings.postgres_user,
            password=settings.postgres_password.get_secret_value(),
        ) as connection,
        connection.cursor() as cursor,
    ):
        cursor.execute(
            """
            SELECT
                to_regclass('public.alembic_version') IS NOT NULL,
                to_regclass('public.flyway_schema_history') IS NOT NULL
            """
        )
        state = cursor.fetchone()
        if state is None:
            raise RuntimeError("Unable to inspect migration history tables")
        alembic_exists, flyway_exists = state
        flyway_versions: frozenset[str] = frozenset()
        if flyway_exists:
            cursor.execute(
                """
                SELECT version, success
                FROM flyway_schema_history
                WHERE version IS NOT NULL
                ORDER BY installed_rank
                """
            )
            rows = cursor.fetchall()
            failed = [str(version) for version, success in rows if not success]
            if failed:
                raise RuntimeError(
                    "Flyway history contains failed migrations: " + ", ".join(failed)
                )
            flyway_versions = frozenset(str(version) for version, _ in rows)
        cursor.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            """
        )
        business_tables = frozenset(str(row[0]) for row in cursor.fetchall())
    return bool(alembic_exists), bool(flyway_exists), flyway_versions, business_tables


def main() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    config = Config(backend_root / "alembic.ini")
    state = inspect_existing_schema()
    baseline_enabled = os.getenv(BASELINE_ENV, "").lower() == "true"
    if should_stamp_flyway_schema(
        alembic_exists=state[0],
        flyway_exists=state[1],
        flyway_versions=state[2],
        business_tables=state[3],
        baseline_enabled=baseline_enabled,
    ):
        command.stamp(config, "head")
    command.upgrade(config, "head")
