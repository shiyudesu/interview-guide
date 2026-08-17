#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/comparison-common.sh"

runtime_dir="$comparison_runtime/knowledge-base-interview-model-stub"
pid_file="$runtime_dir/stub.pid"
log_file="$runtime_dir/stub.log"
record_file="$comparison_reports/knowledge-base-interview-model-stub.jsonl"
mkdir -p "$runtime_dir"

python3 "$repo_root/migration/scripts/interview_model_stub.py" \
  --port 18100 \
  --record "$record_file" \
  >"$log_file" 2>&1 &
stub_pid="$!"
echo "$stub_pid" >"$pid_file"

cleanup() {
  "$repo_root/migration/scripts/stop-comparison-workers.sh" || true
  if kill -0 "$stub_pid" 2>/dev/null; then
    kill "$stub_pid"
    wait "$stub_pid" 2>/dev/null || true
  fi
  rm -f "$pid_file"
}
trap cleanup EXIT

wait_for_http "http://127.0.0.1:18100/health" "$log_file"
(
  cd "$repo_root/backend"
  uv run --frozen python \
    ../migration/scripts/knowledge_base_interview_comparison.py prepare
)
"$repo_root/migration/scripts/start-comparison-workers.sh"

(
  cd "$repo_root/backend"
  uv run --frozen python \
    ../migration/scripts/knowledge_base_interview_comparison.py capture
)
