#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/comparison-common.sh"

"$repo_root/migration/scripts/seed-comparison-data.sh"
(
  cd "$repo_root/backend"
  uv run --frozen python \
    ../migration/scripts/interview_schedule_comparison.py \
    --report-dir ../migration/reports
)

echo "Interview schedule comparison passed"
