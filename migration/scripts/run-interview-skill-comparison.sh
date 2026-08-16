#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/comparison-common.sh"

java_snapshot="$comparison_reports/java-skill-http.json"
python_snapshot="$comparison_reports/python-skill-http.json"
cases_file="$comparison_runtime/skill-cases.json"

cat >"$cases_file" <<'JSON'
{
  "cases": [
    {
      "id": "skill-list",
      "method": "GET",
      "path": "/api/interview/skills"
    },
    {
      "id": "skill-detail",
      "method": "GET",
      "path": "/api/interview/skills/java-backend"
    },
    {
      "id": "skill-not-found",
      "method": "GET",
      "path": "/api/interview/skills/missing"
    }
  ],
  "trackedResponseHeaders": ["content-type", "vary"]
}
JSON

python3 "$repo_root/migration/scripts/comparison.py" capture-http \
  --url http://127.0.0.1:18080 \
  --cases "$cases_file" \
  --output "$java_snapshot"
python3 "$repo_root/migration/scripts/comparison.py" capture-http \
  --url http://127.0.0.1:28080 \
  --cases "$cases_file" \
  --output "$python_snapshot"

python3 "$repo_root/migration/scripts/comparison.py" compare \
  --left-http "$java_snapshot" \
  --right-http "$python_snapshot" \
  --left-schema "$repo_root/migration/samples/database/java-schema.sql" \
  --right-schema "$repo_root/migration/samples/database/java-schema.sql" \
  --json-report "$comparison_reports/interview-skill-comparison.json" \
  --html-report "$comparison_reports/interview-skill-comparison.html" \
  --title "Interview Skill Java/Python comparison"

echo "Interview Skill comparison passed"
