#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
temporary_output="$(mktemp -d)"
trap 'rm -r "$temporary_output"' EXIT

python3 -m unittest discover \
  -s "$repo_root/migration/tests" \
  -p 'test_*.py'

"$repo_root/migration/scripts/sync-flyway-schema.py" --check
"$repo_root/migration/scripts/sync-java-resources.py" --check

python3 "$repo_root/migration/scripts/generate_manifests.py" \
  --root "$repo_root" \
  --output "$temporary_output"

diff --recursive --unified \
  "$repo_root/migration/manifests" \
  "$temporary_output"
