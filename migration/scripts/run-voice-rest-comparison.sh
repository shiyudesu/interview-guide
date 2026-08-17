#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/comparison-common.sh"

reset_sql='TRUNCATE TABLE voice_interview_evaluations, voice_interview_messages, voice_interview_sessions RESTART IDENTITY CASCADE;'
compose exec -T java-postgres \
  psql -v ON_ERROR_STOP=1 -U postgres -d interview_guide_java -c "$reset_sql"
compose exec -T python-postgres \
  psql -v ON_ERROR_STOP=1 -U postgres -d interview_guide_python -c "$reset_sql"

cases_file="$comparison_runtime/voice-rest-cases.json"
cat >"$cases_file" <<'JSON'
{
  "cases": [
    {
      "id":"voice-create",
      "method":"POST",
      "path":"/api/voice-interview/sessions",
      "headers":{"Content-Type":"application/json"},
      "body":"{\"roleType\":\"IGNORED\",\"skillId\":\"java-backend\",\"difficulty\":\"mid\",\"introEnabled\":false,\"techEnabled\":true,\"projectEnabled\":true,\"hrEnabled\":true,\"plannedDuration\":30}"
    },
    {"id":"voice-get","method":"GET","path":"/api/voice-interview/sessions/1"},
    {"id":"voice-list","method":"GET","path":"/api/voice-interview/sessions"},
    {"id":"voice-messages","method":"GET","path":"/api/voice-interview/sessions/1/messages"},
    {
      "id":"voice-pause",
      "method":"PUT",
      "path":"/api/voice-interview/sessions/1/pause",
      "headers":{"Content-Type":"application/json"},
      "body":"{\"reason\":\"fixed\"}"
    },
    {"id":"voice-resume","method":"PUT","path":"/api/voice-interview/sessions/1/resume"},
    {"id":"voice-end","method":"POST","path":"/api/voice-interview/sessions/1/end"},
    {"id":"voice-evaluation","method":"GET","path":"/api/voice-interview/sessions/1/evaluation"},
    {"id":"voice-evaluation-trigger","method":"POST","path":"/api/voice-interview/sessions/1/evaluation"},
    {"id":"voice-delete","method":"DELETE","path":"/api/voice-interview/sessions/1"},
    {"id":"voice-deleted","method":"GET","path":"/api/voice-interview/sessions/1"}
  ],
  "trackedResponseHeaders":["content-type","vary"]
}
JSON

python3 "$repo_root/migration/scripts/comparison.py" capture-http \
  --url http://127.0.0.1:18080 \
  --cases "$cases_file" \
  --output "$comparison_reports/java-voice-rest.json"
python3 "$repo_root/migration/scripts/comparison.py" capture-http \
  --url http://127.0.0.1:28080 \
  --cases "$cases_file" \
  --output "$comparison_reports/python-voice-rest.json"

python3 "$repo_root/migration/scripts/comparison.py" compare \
  --left-http "$comparison_reports/java-voice-rest.json" \
  --right-http "$comparison_reports/python-voice-rest.json" \
  --left-schema "$repo_root/migration/samples/database/java-schema.sql" \
  --right-schema "$repo_root/migration/samples/database/java-schema.sql" \
  --json-report "$comparison_reports/voice-rest-comparison.json" \
  --html-report "$comparison_reports/voice-rest-comparison.html" \
  --title "Voice interview REST Java/Python comparison"

echo "Voice interview REST comparison passed"
