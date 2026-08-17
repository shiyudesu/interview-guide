#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/comparison-common.sh"

if [[ -z "${AI_BAILIAN_API_KEY:-}" ]]; then
  echo "AI_BAILIAN_API_KEY is required for performance acceptance" >&2
  exit 2
fi

python3 "$repo_root/migration/scripts/performance_compare.py" \
  --iterations "${PERFORMANCE_ITERATIONS:-5}" \
  --proxy-log "$comparison_reports/model-proxy.jsonl" \
  --output "$comparison_reports/performance-provider-connectivity.json"

echo "Real-provider performance acceptance passed"
