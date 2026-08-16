#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/comparison-common.sh"

mkdir -p "$comparison_reports"
"$repo_root/migration/scripts/seed-comparison-data.sh"

python3 "$repo_root/migration/scripts/comparison.py" capture-http \
  --url http://127.0.0.1:18080 \
  --cases "$comparison_cases" \
  --output "$comparison_reports/java-http.json"
python3 "$repo_root/migration/scripts/comparison.py" capture-http \
  --url http://127.0.0.1:28080 \
  --cases "$comparison_cases" \
  --output "$comparison_reports/candidate-http.json"

compose exec -T java-postgres \
  pg_dump \
  --username postgres \
  --schema-only \
  --no-owner \
  --no-privileges \
  interview_guide_java \
  >"$comparison_reports/java-schema.sql"
compose exec -T python-postgres \
  pg_dump \
  --username postgres \
  --schema-only \
  --no-owner \
  --no-privileges \
  interview_guide_python \
  >"$comparison_reports/candidate-schema.sql"

python3 "$repo_root/migration/scripts/comparison.py" compare \
  --left-http "$repo_root/migration/samples/http/java-baseline.json" \
  --right-http "$comparison_reports/java-http.json" \
  --left-schema "$repo_root/migration/samples/database/java-schema.sql" \
  --right-schema "$comparison_reports/java-schema.sql" \
  --json-report "$comparison_reports/java-baseline-drift.json" \
  --html-report "$comparison_reports/java-baseline-drift.html" \
  --title "Java baseline drift"

python3 "$repo_root/migration/scripts/comparison.py" compare \
  --left-http "$comparison_reports/java-http.json" \
  --right-http "$comparison_reports/candidate-http.json" \
  --left-schema "$comparison_reports/java-schema.sql" \
  --right-schema "$comparison_reports/candidate-schema.sql" \
  --json-report "$comparison_reports/comparison.json" \
  --html-report "$comparison_reports/comparison.html" \
  --title "Java and candidate comparison"

echo "Comparison passed; reports are in migration/reports/"
