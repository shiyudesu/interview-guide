#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/comparison-common.sh"

mkdir -p "$comparison_reports"

compose exec -T java-postgres \
  pg_dump \
  --username postgres \
  --schema-only \
  --no-owner \
  --no-privileges \
  --exclude-table flyway_schema_history \
  --exclude-table alembic_version \
  interview_guide_java \
  >"$comparison_reports/java-business-schema.sql"
compose exec -T python-postgres \
  pg_dump \
  --username postgres \
  --schema-only \
  --no-owner \
  --no-privileges \
  --exclude-table flyway_schema_history \
  --exclude-table alembic_version \
  interview_guide_python \
  >"$comparison_reports/python-business-schema.sql"

python3 "$repo_root/migration/scripts/comparison.py" compare-schema \
  --left-schema "$comparison_reports/java-business-schema.sql" \
  --right-schema "$comparison_reports/python-business-schema.sql" \
  --json-report "$comparison_reports/schema-comparison.json" \
  --html-report "$comparison_reports/schema-comparison.html" \
  --title "Flyway and Alembic business schema comparison"

echo "Database schema comparison passed"
