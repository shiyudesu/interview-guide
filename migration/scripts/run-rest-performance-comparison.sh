#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/comparison-common.sh"

(
  cd "$repo_root/backend"
  uv run --frozen python ../migration/scripts/rest_performance_compare.py \
    --java-pid-file "$comparison_runtime/java/app.pid" \
    --python-pid-file "$comparison_runtime/candidate/app.pid" \
    --output "$comparison_reports/rest-performance-comparison.json"
)

echo "No-model REST performance comparison passed"
