-- 为面试会话表新增知识库面试方向字段。
-- V1 已包含该字段；本迁移用于未执行 V1 的既有库基线后补列。
DO $$
BEGIN
  IF to_regclass('public.interview_sessions') IS NOT NULL THEN
    IF NOT EXISTS (
      SELECT 1
      FROM information_schema.columns
      WHERE table_schema = 'public'
        AND table_name = 'interview_sessions'
        AND column_name = 'interview_category'
    ) THEN
      ALTER TABLE interview_sessions
        ADD COLUMN interview_category VARCHAR(64);
    END IF;

    COMMENT ON COLUMN interview_sessions.interview_category IS '知识库面试方向（来自题库 category，普通面试为 NULL）';
  END IF;
END
$$;
