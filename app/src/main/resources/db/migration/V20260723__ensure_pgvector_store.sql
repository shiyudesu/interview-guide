DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'hstore') THEN
    CREATE EXTENSION hstore WITH SCHEMA public;
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'uuid-ossp') THEN
    CREATE EXTENSION "uuid-ossp" WITH SCHEMA public;
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
    CREATE EXTENSION vector WITH SCHEMA public;
  END IF;

  IF to_regclass('public.vector_store') IS NULL THEN
    CREATE TABLE vector_store (
      id UUID DEFAULT public.uuid_generate_v4() NOT NULL PRIMARY KEY,
      content TEXT,
      metadata JSON,
      embedding public.vector(1024)
    );
  END IF;

  IF to_regclass('public.spring_ai_vector_index') IS NULL THEN
    CREATE INDEX spring_ai_vector_index
      ON vector_store USING hnsw (embedding public.vector_cosine_ops);
  END IF;
END
$$;
