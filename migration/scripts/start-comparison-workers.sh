#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/comparison-common.sh"

runtime_dir="$comparison_runtime/question-workers"
mkdir -p "$runtime_dir/java" "$runtime_dir/python"

java_pid_file="$runtime_dir/java/worker.pid"
python_pid_file="$runtime_dir/python/worker.pid"
java_log="$runtime_dir/java/worker.log"
python_log="$runtime_dir/python/worker.log"
comparison_ai_api_key="${AI_BAILIAN_API_KEY:-comparison-placeholder-key}"

java_jar="$(
  find "$repo_root/app/build/libs" \
    -maxdepth 1 \
    -type f \
    -name '*.jar' \
    ! -name '*-plain.jar' \
    -print \
    -quit
)"
if [[ -z "$java_jar" ]]; then
  "$repo_root/gradlew" :app:bootJar --no-daemon
  java_jar="$(
    find "$repo_root/app/build/libs" \
      -maxdepth 1 \
      -type f \
      -name '*.jar' \
      ! -name '*-plain.jar' \
      -print \
      -quit
  )"
fi

java_tool_options="$(
  printf '%s' \
    '-Duser.timezone=Asia/Shanghai ' \
    '-Dinterview.guide.migration.consumer-suffix=question-comparison ' \
    '-Dinterview.guide.migration.fixed-time=2026-08-16T08:00:00 ' \
    '-Dinterview.guide.migration.uuid.interview-session=' \
    '11111111-1111-1111-1111-111111111111 ' \
    '-Dinterview.guide.migration.uuid.question-generation-task=' \
    'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa ' \
    '-Dinterview.guide.migration.uuid.prompt-boundary=' \
    '00000000-0000-0000-0000-000000000000,' \
    '00000000-0000-0000-0000-000000000000,' \
    '00000000-0000-0000-0000-000000000000,' \
    '00000000-0000-0000-0000-000000000000,' \
    '00000000-0000-0000-0000-000000000000,' \
    '00000000-0000-0000-0000-000000000000,' \
    '00000000-0000-0000-0000-000000000000,' \
    '00000000-0000-0000-0000-000000000000'
)"

nohup env \
  SERVER_PORT=18081 \
  POSTGRES_HOST=localhost \
  POSTGRES_PORT=15432 \
  POSTGRES_DB=interview_guide_java \
  POSTGRES_USER=postgres \
  POSTGRES_PASSWORD=comparison-password \
  REDIS_HOST=localhost \
  REDIS_PORT=16379 \
  TZ=Asia/Shanghai \
  APP_STORAGE_ENDPOINT=http://localhost:19000 \
  APP_STORAGE_ACCESS_KEY=comparison-access \
  APP_STORAGE_SECRET_KEY=comparison-secret \
  APP_STORAGE_BUCKET=interview-guide-java \
  APP_STORAGE_AUTO_CREATE_BUCKET=false \
  APP_AI_PROVIDERS_DASHSCOPE_BASE_URL=http://127.0.0.1:18100/v1 \
  APP_AI_CONFIG_ENCRYPTION_KEY=comparison-provider-encryption-key \
  AI_BAILIAN_API_KEY="$comparison_ai_api_key" \
  JAVA_TOOL_OPTIONS="$java_tool_options" \
  java -jar "$java_jar" \
  >"$java_log" 2>&1 &
echo "$!" >"$java_pid_file"

(
  cd "$repo_root/backend"
  nohup env \
    POSTGRES_HOST=localhost \
    POSTGRES_PORT=25432 \
    POSTGRES_DB=interview_guide_python \
    POSTGRES_USER=postgres \
    POSTGRES_PASSWORD=comparison-password \
    REDIS_HOST=localhost \
    REDIS_PORT=26379 \
    TZ=Asia/Shanghai \
    MIGRATION_FIXED_TIME=2026-08-16T08:00:00 \
    MIGRATION_PROMPT_BOUNDARY_UUID=00000000-0000-0000-0000-000000000000 \
    APP_STORAGE_ENDPOINT=http://localhost:19000 \
    APP_STORAGE_ACCESS_KEY=comparison-access \
    APP_STORAGE_SECRET_KEY=comparison-secret \
    APP_STORAGE_BUCKET=interview-guide-python \
    APP_AI_PROVIDERS_DASHSCOPE_BASE_URL=http://127.0.0.1:18100/v1 \
    APP_AI_CONFIG_ENCRYPTION_KEY=comparison-provider-encryption-key \
    AI_BAILIAN_API_KEY="$comparison_ai_api_key" \
    uv run --frozen interview-guide-worker \
    >"$python_log" 2>&1 &
  echo "$!" >"$python_pid_file"
)

wait_for_http "http://127.0.0.1:18081/actuator/health" "$java_log"
sleep 2

python_pid="$(cat "$python_pid_file")"
if ! kill -0 "$python_pid" 2>/dev/null; then
  cat "$python_log" >&2
  exit 1
fi

echo "Comparison workers are ready"
