#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/comparison-common.sh"

candidate="${COMPARISON_CANDIDATE:-auto}"
if [[ "$candidate" == "auto" ]]; then
  if [[ -f "$repo_root/backend/pyproject.toml" ]]; then
    candidate="python"
  else
    candidate="java"
  fi
fi
if [[ "$candidate" != "java" && "$candidate" != "python" ]]; then
  echo "COMPARISON_CANDIDATE must be java, python, or auto" >&2
  exit 2
fi

mkdir -p \
  "$comparison_runtime/java" \
  "$comparison_runtime/candidate" \
  "$comparison_reports"

"$repo_root/migration/scripts/start-model-proxy.sh"

compose up -d --wait \
  java-postgres \
  python-postgres \
  java-redis \
  python-redis \
  minio
compose run --rm minio-init

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
if [[ -z "$java_jar" ]]; then
  echo "Java boot jar was not generated" >&2
  exit 1
fi

start_java() {
  local name="$1"
  local port="$2"
  local postgres_port="$3"
  local postgres_db="$4"
  local redis_port="$5"
  local bucket="$6"
  local runtime_dir="$comparison_runtime/$name"
  local pid_file="$runtime_dir/app.pid"
  local log_file="$runtime_dir/app.log"

  if [[ -f "$pid_file" ]]; then
    local existing_pid
    existing_pid="$(cat "$pid_file")"
    if [[ "$existing_pid" =~ ^[0-9]+$ ]] && kill -0 "$existing_pid" 2>/dev/null; then
      return
    fi
    rm -f "$pid_file"
  fi

  nohup env \
    SERVER_PORT="$port" \
    POSTGRES_HOST=localhost \
    POSTGRES_PORT="$postgres_port" \
    POSTGRES_DB="$postgres_db" \
    POSTGRES_USER=postgres \
    POSTGRES_PASSWORD=comparison-password \
    REDIS_HOST=localhost \
    REDIS_PORT="$redis_port" \
    APP_STORAGE_ENDPOINT=http://localhost:19000 \
    APP_STORAGE_ACCESS_KEY=comparison-access \
    APP_STORAGE_SECRET_KEY=comparison-secret \
    APP_STORAGE_BUCKET="$bucket" \
    APP_STORAGE_AUTO_CREATE_BUCKET=false \
    APP_AI_PROVIDERS_DASHSCOPE_BASE_URL=http://127.0.0.1:18090/proxy/https/dashscope.aliyuncs.com/compatible-mode/v1 \
    APP_AI_CONFIG_ENCRYPTION_KEY=comparison-provider-encryption-key \
    APP_AI_CONFIG_YAML_PATH="$runtime_dir/llm-providers.yml" \
    APP_AI_CONFIG_ENV_PATH="$runtime_dir/llm-providers.env" \
    APP_VOICE_INTERVIEW_QWEN_ASR_URL=ws://127.0.0.1:18090/ws/wss/dashscope.aliyuncs.com/api-ws/v1/realtime \
    AI_BAILIAN_API_KEY=comparison-placeholder-key \
    JAVA_TOOL_OPTIONS=-Dinterview.guide.migration.consumer-suffix=comparison \
    java -jar "$java_jar" \
    >"$log_file" 2>&1 &
  echo "$!" >"$pid_file"
}

start_python() {
  local runtime_dir="$comparison_runtime/candidate"
  local pid_file="$runtime_dir/app.pid"
  local log_file="$runtime_dir/app.log"
  if [[ ! -f "$repo_root/backend/pyproject.toml" ]]; then
    echo "backend/pyproject.toml is required for the Python candidate" >&2
    exit 1
  fi
  if [[ -f "$pid_file" ]]; then
    local existing_pid
    existing_pid="$(cat "$pid_file")"
    if [[ "$existing_pid" =~ ^[0-9]+$ ]] && kill -0 "$existing_pid" 2>/dev/null; then
      return
    fi
    rm -f "$pid_file"
  fi
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
      APP_STORAGE_ENDPOINT=http://localhost:19000 \
      APP_STORAGE_ACCESS_KEY=comparison-access \
      APP_STORAGE_SECRET_KEY=comparison-secret \
      APP_STORAGE_BUCKET=interview-guide-python \
      APP_AI_PROVIDERS_DASHSCOPE_BASE_URL=http://127.0.0.1:18090/proxy/https/dashscope.aliyuncs.com/compatible-mode/v1 \
      APP_AI_CONFIG_ENCRYPTION_KEY=comparison-provider-encryption-key \
      APP_VOICE_INTERVIEW_QWEN_ASR_URL=ws://127.0.0.1:18090/ws/wss/dashscope.aliyuncs.com/api-ws/v1/realtime \
      AI_BAILIAN_API_KEY=comparison-placeholder-key \
      uv run uvicorn interview_guide.main:app \
        --host 127.0.0.1 \
        --port 28080 \
        --workers 1 \
      >"$log_file" 2>&1 &
    echo "$!" >"$pid_file"
  )
}

start_java java 18080 15432 interview_guide_java 16379 interview-guide-java
if [[ "$candidate" == "java" ]]; then
  start_java candidate 28080 25432 interview_guide_python 26379 interview-guide-python
else
  start_python
fi

wait_for_http \
  "http://127.0.0.1:18080/actuator/health" \
  "$comparison_runtime/java/app.log"
wait_for_http \
  "http://127.0.0.1:28080/actuator/health" \
  "$comparison_runtime/candidate/app.log"

echo "Comparison environment is ready: Java :18080, candidate :28080 ($candidate)"
