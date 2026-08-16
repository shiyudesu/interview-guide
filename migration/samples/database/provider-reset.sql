DELETE FROM llm_global_setting;
DELETE FROM llm_provider_config;

INSERT INTO llm_provider_config (
  id,
  api_key_ciphertext,
  api_key_nonce,
  base_url,
  builtin,
  created_at,
  embedding_dimensions,
  embedding_model,
  enabled,
  model,
  supports_embedding,
  temperature,
  updated_at
) VALUES
  (
    'lmstudio',
    'IDVctuzwkCuTthF7ZYy6hfm3gVla/R1OSg==',
    'DA0ODxAREhMUFRYX',
    'http://localhost:1234',
    true,
    TIMESTAMP '2026-08-16 08:00:00',
    1024,
    NULL,
    true,
    'qwen2.5-7b-instruct',
    false,
    NULL,
    TIMESTAMP '2026-08-16 08:00:00'
  ),
  (
    'kimi',
    'naSAtuOUCFr3H59/z0a9oA==',
    'GBkaGxwdHh8gISIj',
    'https://api.moonshot.cn/v1',
    true,
    TIMESTAMP '2026-08-16 08:00:00',
    1024,
    NULL,
    true,
    'kimi-latest',
    false,
    1,
    TIMESTAMP '2026-08-16 08:00:00'
  ),
  (
    'deepseek',
    'HIHmb6zbrAMu6QyoeYRtLQ==',
    'JCUmJygpKissLS4v',
    'https://api.deepseek.com',
    true,
    TIMESTAMP '2026-08-16 08:00:00',
    1024,
    NULL,
    true,
    'deepseek-v4-flash',
    false,
    NULL,
    TIMESTAMP '2026-08-16 08:00:00'
  ),
  (
    'glm',
    '0ENKpu6MtzbWYNKMBudd7A==',
    'MDEyMzQ1Njc4OTo7',
    'https://open.bigmodel.cn/api/coding/paas/v4',
    true,
    TIMESTAMP '2026-08-16 08:00:00',
    1024,
    'embedding-3',
    true,
    'glm-5',
    true,
    NULL,
    TIMESTAMP '2026-08-16 08:00:00'
  ),
  (
    'dashscope',
    'JiW12cSvNow97GeAk3/pwsyQgxbCLT/JwsZaRb6yHTwXgvuvPo8jxh/6',
    'AAECAwQFBgcICQoL',
    'http://127.0.0.1:18090/proxy/https/dashscope.aliyuncs.com/compatible-mode/v1',
    true,
    TIMESTAMP '2026-08-16 08:00:00',
    1024,
    'text-embedding-v3',
    true,
    'qwen3.5-flash',
    true,
    NULL,
    TIMESTAMP '2026-08-16 08:00:00'
  );

INSERT INTO llm_global_setting (
  id,
  created_at,
  default_chat_provider_id,
  default_embedding_provider_id,
  updated_at
) VALUES (
  1,
  TIMESTAMP '2026-08-16 08:00:00',
  'dashscope',
  'dashscope',
  TIMESTAMP '2026-08-16 08:00:00'
);
