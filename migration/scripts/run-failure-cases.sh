#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
python3 -m unittest \
  -v \
  "$repo_root/migration/tests/test_comparison.py" \
  "$repo_root/migration/tests/test_performance_compare.py" \
  "$repo_root/migration/tests/test_rest_performance_compare.py" \
  "$repo_root/migration/tests/test_realtime_artifact.py"
