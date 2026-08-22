#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
temporary_output="$(mktemp -d)"
trap 'rm -r "$temporary_output"' EXIT

python3 "$repo_root/tools/scripts/generate_manifests.py" \
  --root "$repo_root" \
  --output "$temporary_output"

python3 - "$temporary_output/api.json" <<'PY'
import json
import sys
from pathlib import Path

manifest = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
frontend_only = manifest["unmatched"]["frontendOnly"]
if frontend_only:
    for item in frontend_only:
        source = item["source"]
        print(
            "frontend-only API contract: "
            f"{item['httpMethod']} {item['path']} "
            f"({source['file']}:{source['line']})",
            file=sys.stderr,
        )
    raise SystemExit(1)
PY

diff --recursive --unified \
  "$repo_root/tools/manifests" \
  "$temporary_output"
