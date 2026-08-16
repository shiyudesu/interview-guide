#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/comparison-common.sh"

runtime_dir="$comparison_runtime/model-proxy"
pid_file="$runtime_dir/proxy.pid"
log_file="$runtime_dir/proxy.log"
mkdir -p "$runtime_dir"

if [[ -f "$pid_file" ]]; then
  existing_pid="$(cat "$pid_file")"
  if [[ "$existing_pid" =~ ^[0-9]+$ ]] && kill -0 "$existing_pid" 2>/dev/null; then
    exit 0
  fi
  rm -f "$pid_file"
fi

(
  cd "$repo_root/migration/model-proxy"
  nohup env \
    MODEL_PROXY_ENABLE_FAULTS=true \
    MODEL_PROXY_HOST=127.0.0.1 \
    MODEL_PROXY_PORT=18090 \
    MODEL_PROXY_RECORD_PATH="$comparison_reports/model-proxy.jsonl" \
    uv run --frozen interview-guide-model-proxy \
    >"$log_file" 2>&1 &
  echo "$!" >"$pid_file"
)

wait_for_http \
  "http://127.0.0.1:18090/__control/health" \
  "$log_file"
