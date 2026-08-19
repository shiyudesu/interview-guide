#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
temporary_output="$(mktemp -d)"
trap 'rm -r "$temporary_output"' EXIT

python3 "$repo_root/tools/scripts/generate_manifests.py" \
  --root "$repo_root" \
  --output "$temporary_output"

diff --recursive --unified \
  "$repo_root/tools/manifests" \
  "$temporary_output"
