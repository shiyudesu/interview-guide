#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
python3 "$repo_root/tools/scripts/generate_manifests.py" \
  --root "$repo_root" \
  --output "$repo_root/tools/manifests"
