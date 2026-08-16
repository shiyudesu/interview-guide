-- 知识库题目异步生成状态和恢复快照
ALTER TABLE knowledge_bases
  ADD COLUMN IF NOT EXISTS question_gen_status VARCHAR(20) NOT NULL DEFAULT 'NONE',
  ADD COLUMN IF NOT EXISTS question_gen_error VARCHAR(500),
  ADD COLUMN IF NOT EXISTS question_gen_task_id VARCHAR(36),
  ADD COLUMN IF NOT EXISTS question_gen_config TEXT,
  ADD COLUMN IF NOT EXISTS question_gen_message VARCHAR(500),
  ADD COLUMN IF NOT EXISTS question_gen_saved_count INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS question_gen_skipped_count INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS question_gen_updated_at TIMESTAMP(6);

ALTER TABLE knowledge_bases
  DROP CONSTRAINT IF EXISTS knowledge_bases_question_gen_status_check;

ALTER TABLE knowledge_bases
  ADD CONSTRAINT knowledge_bases_question_gen_status_check
    CHECK (question_gen_status IN ('NONE', 'QUEUED', 'PROCESSING', 'COMPLETED', 'FAILED'));

CREATE INDEX IF NOT EXISTS idx_kb_question_gen_status_updated
  ON knowledge_bases(question_gen_status, question_gen_updated_at);
