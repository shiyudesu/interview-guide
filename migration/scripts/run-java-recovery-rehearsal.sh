#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
reports="$repo_root/migration/reports"
started_at="$(date --iso-8601=seconds)"

cleanup() {
  "$repo_root/migration/scripts/stop-comparison-env.sh" >/dev/null 2>&1 || true
}
trap cleanup EXIT

"$repo_root/migration/scripts/stop-comparison-env.sh" --purge \
  >/dev/null 2>&1 || true

COMPARISON_CANDIDATE=java \
  "$repo_root/migration/scripts/start-comparison-env.sh"
"$repo_root/migration/scripts/run-comparison.sh"

python3 - "$reports" "$started_at" <<'PY'
import json
import sys
from datetime import datetime
from pathlib import Path

reports = Path(sys.argv[1])
document = {
    "candidate": "java",
    "completedAt": datetime.now().astimezone().isoformat(),
    "comparison": json.loads((reports / "comparison.json").read_text()),
    "startedAt": sys.argv[2],
}
document["passed"] = bool(document["comparison"]["passed"])
(reports / "java-recovery-rehearsal.json").write_text(
    json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
if not document["passed"]:
    raise SystemExit(1)
PY

echo "Java recovery rehearsal passed"
