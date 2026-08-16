#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/comparison-common.sh"

"$repo_root/migration/scripts/seed-comparison-data.sh"

python3 "$repo_root/migration/scripts/comparison.py" capture-http \
  --url http://127.0.0.1:18080 \
  --cases "$comparison_cases" \
  --output "$repo_root/migration/samples/http/java-baseline.json"

compose exec -T java-postgres \
  pg_dump \
  --username postgres \
  --schema-only \
  --no-owner \
  --no-privileges \
  --exclude-table flyway_schema_history \
  --exclude-table alembic_version \
  interview_guide_java \
  >"$repo_root/migration/samples/database/java-schema.sql"
