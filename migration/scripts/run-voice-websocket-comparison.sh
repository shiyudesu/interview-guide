#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/comparison-common.sh"

reset_sql='TRUNCATE TABLE voice_interview_evaluations, voice_interview_messages, voice_interview_sessions RESTART IDENTITY CASCADE;'
compose exec -T java-postgres \
  psql -v ON_ERROR_STOP=1 -U postgres -d interview_guide_java -c "$reset_sql"
compose exec -T python-postgres \
  psql -v ON_ERROR_STOP=1 -U postgres -d interview_guide_python -c "$reset_sql"

create_body='{"skillId":"java-backend","difficulty":"mid","introEnabled":false,"techEnabled":true,"projectEnabled":true,"hrEnabled":true,"plannedDuration":30}'
curl --fail --silent --show-error \
  -H 'Content-Type: application/json' \
  --data "$create_body" \
  http://127.0.0.1:18080/api/voice-interview/sessions >/dev/null
curl --fail --silent --show-error \
  -H 'Content-Type: application/json' \
  --data "$create_body" \
  http://127.0.0.1:28080/api/voice-interview/sessions >/dev/null

history_sql=$(
  cat <<'SQL'
INSERT INTO voice_interview_messages (
  ai_generated_text, created_at, message_type, phase, sequence_num,
  session_id, "timestamp", user_recognized_text
) VALUES (
  '固定历史问题', '2026-08-16 08:00:00', 'DIALOGUE', 'TECH', 1,
  1, '2026-08-16 08:00:00', NULL
);
SQL
)
compose exec -T java-postgres \
  psql -v ON_ERROR_STOP=1 -U postgres -d interview_guide_java -c "$history_sql"
compose exec -T python-postgres \
  psql -v ON_ERROR_STOP=1 -U postgres -d interview_guide_python -c "$history_sql"

messages_file="$comparison_runtime/voice-websocket-empty-messages.jsonl"
: >"$messages_file"

(
  cd "$repo_root/backend"
  uv run --frozen python ../migration/scripts/realtime_artifact.py capture-websocket \
    --url ws://127.0.0.1:18080/ws/voice-interview/1 \
    --messages "$messages_file" \
    --max-messages 1 \
    --timeout 3 \
    --output "$comparison_reports/java-voice-websocket.json"
  uv run --frozen python ../migration/scripts/realtime_artifact.py capture-websocket \
    --url ws://127.0.0.1:28080/ws/voice-interview/1 \
    --messages "$messages_file" \
    --max-messages 1 \
    --timeout 3 \
    --output "$comparison_reports/python-voice-websocket.json"
)

python3 "$repo_root/migration/scripts/normalize-voice-transcript.py" \
  --input "$comparison_reports/java-voice-websocket.json" \
  --output "$comparison_reports/java-voice-websocket-normalized.json"
python3 "$repo_root/migration/scripts/normalize-voice-transcript.py" \
  --input "$comparison_reports/python-voice-websocket.json" \
  --output "$comparison_reports/python-voice-websocket-normalized.json"

(
  cd "$repo_root/backend"
  uv run --frozen python ../migration/scripts/realtime_artifact.py compare \
    --left "$comparison_reports/java-voice-websocket-normalized.json" \
    --right "$comparison_reports/python-voice-websocket-normalized.json" \
    --output "$comparison_reports/voice-websocket-comparison.json"
)

echo "Voice interview WebSocket non-model transcript comparison passed"
