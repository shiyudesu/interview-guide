#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/comparison-common.sh"

capture_state() {
  local name="$1"
  local postgres_service="$2"
  local postgres_database="$3"
  local redis_port="$4"
  local bucket="$5"
  local database_dump="$comparison_reports/$name-data.sql"

  compose exec -T "$postgres_service" \
    pg_dump \
    --username postgres \
    --data-only \
    --column-inserts \
    --no-owner \
    --no-privileges \
    --table interview_schedule \
    --table llm_global_setting \
    --table llm_provider_config \
    "$postgres_database" \
    >"$database_dump"

  python3 "$repo_root/migration/scripts/runtime_state.py" capture \
    --database-data "$database_dump" \
    --redis-host 127.0.0.1 \
    --redis-port "$redis_port" \
    --s3-endpoint http://127.0.0.1:19000 \
    --s3-access-key comparison-access \
    --s3-secret-key comparison-secret \
    --s3-bucket "$bucket" \
    --output "$comparison_reports/$name-runtime-state.json"
}

capture_state \
  java \
  java-postgres \
  interview_guide_java \
  16379 \
  interview-guide-java
capture_state \
  candidate \
  python-postgres \
  interview_guide_python \
  26379 \
  interview-guide-python
