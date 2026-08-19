"""Use a descriptive name for the vector HNSW index.

Revision ID: 0002_rename_vector_index
Revises: 0001_initial_schema
Create Date: 2026-08-19
"""

from __future__ import annotations

from alembic import op

revision: str = "0002_rename_vector_index"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        DECLARE
          candidate_name TEXT;
        BEGIN
          IF to_regclass('public.vector_store_embedding_hnsw_idx') IS NULL THEN
            SELECT index_class.relname
              INTO candidate_name
              FROM pg_class AS table_class
              JOIN pg_namespace AS table_namespace
                ON table_namespace.oid = table_class.relnamespace
              JOIN pg_index AS index_metadata
                ON index_metadata.indrelid = table_class.oid
              JOIN pg_class AS index_class
                ON index_class.oid = index_metadata.indexrelid
             WHERE table_namespace.nspname = 'public'
               AND table_class.relname = 'vector_store'
               AND pg_get_indexdef(index_class.oid)
                   ILIKE '%USING hnsw (embedding%vector_cosine_ops%'
             ORDER BY index_class.relname
             LIMIT 1;

            IF candidate_name IS NULL THEN
              CREATE INDEX vector_store_embedding_hnsw_idx
                ON vector_store USING hnsw (embedding public.vector_cosine_ops);
            ELSE
              EXECUTE format(
                'ALTER INDEX %I RENAME TO vector_store_embedding_hnsw_idx',
                candidate_name
              );
            END IF;
          END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    # The descriptive index name is safe for the previous schema revision.
    pass
