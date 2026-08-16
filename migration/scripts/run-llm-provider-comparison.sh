#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/comparison-common.sh"

cases_file="$comparison_runtime/provider-cases.json"
cat >"$cases_file" <<'JSON'
{
  "cases": [
    {"id":"provider-list","method":"GET","path":"/api/llm-provider/list"},
    {"id":"provider-detail","method":"GET","path":"/api/llm-provider/dashscope"},
    {"id":"provider-missing","method":"GET","path":"/api/llm-provider/missing"},
    {"id":"provider-defaults","method":"GET","path":"/api/llm-provider/default-provider"},
    {
      "id":"provider-update-chat-default",
      "method":"PUT",
      "path":"/api/llm-provider/default-provider",
      "headers":{"Content-Type":"application/json"},
      "body":"{\"defaultProvider\":\"lmstudio\",\"defaultEmbeddingProvider\":null}"
    },
    {
      "id":"provider-update-embedding-default",
      "method":"PUT",
      "path":"/api/llm-provider/default-embedding-provider",
      "headers":{"Content-Type":"application/json"},
      "body":"{\"defaultProvider\":null,\"defaultEmbeddingProvider\":\"glm\"}"
    },
    {"id":"provider-updated-defaults","method":"GET","path":"/api/llm-provider/default-provider"},
    {"id":"provider-reload","method":"POST","path":"/api/llm-provider/reload"}
  ],
  "trackedResponseHeaders":["content-type","vary"]
}
JSON

python3 "$repo_root/migration/scripts/comparison.py" capture-http \
  --url http://127.0.0.1:18080 \
  --cases "$cases_file" \
  --output "$comparison_reports/java-provider-http.json"
python3 "$repo_root/migration/scripts/comparison.py" capture-http \
  --url http://127.0.0.1:28080 \
  --cases "$cases_file" \
  --output "$comparison_reports/python-provider-http.json"

python3 "$repo_root/migration/scripts/comparison.py" compare \
  --left-http "$comparison_reports/java-provider-http.json" \
  --right-http "$comparison_reports/python-provider-http.json" \
  --left-schema "$repo_root/migration/samples/database/java-schema.sql" \
  --right-schema "$repo_root/migration/samples/database/java-schema.sql" \
  --json-report "$comparison_reports/llm-provider-comparison.json" \
  --html-report "$comparison_reports/llm-provider-comparison.html" \
  --title "LLM Provider Java/Python comparison"

compose exec -T java-postgres \
  pg_dump \
  --username postgres \
  --data-only \
  --column-inserts \
  --no-owner \
  --no-privileges \
  --table llm_provider_config \
  --table llm_global_setting \
  interview_guide_java \
  >"$comparison_reports/java-provider-data.sql"
compose exec -T python-postgres \
  pg_dump \
  --username postgres \
  --data-only \
  --column-inserts \
  --no-owner \
  --no-privileges \
  --table llm_provider_config \
  --table llm_global_setting \
  interview_guide_python \
  >"$comparison_reports/python-provider-data.sql"

python3 "$repo_root/migration/scripts/comparison.py" compare-schema \
  --left-schema "$comparison_reports/java-provider-data.sql" \
  --right-schema "$comparison_reports/python-provider-data.sql" \
  --json-report "$comparison_reports/llm-provider-data-comparison.json" \
  --html-report "$comparison_reports/llm-provider-data-comparison.html" \
  --title "LLM Provider database data comparison"

echo "LLM Provider comparison passed"
