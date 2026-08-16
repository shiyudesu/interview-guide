#!/usr/bin/env bash

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
comparison_compose="$repo_root/migration/comparison/docker-compose.yml"
comparison_runtime="$repo_root/migration/reports/runtime"
comparison_cases="$repo_root/migration/samples/http/cases.json"
comparison_reports="$repo_root/migration/reports"

compose() {
  docker compose \
    --project-name interview-guide-comparison \
    -f "$comparison_compose" \
    "$@"
}

wait_for_http() {
  local url="$1"
  local log_file="$2"
  local attempts=90
  local attempt
  for ((attempt = 1; attempt <= attempts; attempt++)); do
    if curl --fail --silent --show-error "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  echo "Timed out waiting for $url" >&2
  if [[ -f "$log_file" ]]; then
    tail -n 120 "$log_file" >&2
  fi
  return 1
}

stop_pid_file() {
  local pid_file="$1"
  if [[ ! -f "$pid_file" ]]; then
    return
  fi
  local pid
  pid="$(cat "$pid_file")"
  if [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null; then
    kill "$pid"
    local attempt
    for ((attempt = 1; attempt <= 30; attempt++)); do
      if ! kill -0 "$pid" 2>/dev/null; then
        break
      fi
      sleep 1
    done
    if kill -0 "$pid" 2>/dev/null; then
      kill -KILL "$pid"
    fi
  fi
  rm -f "$pid_file"
}
