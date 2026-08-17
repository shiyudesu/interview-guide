#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/comparison-common.sh"

if [[ -z "${AI_BAILIAN_API_KEY:-}" ]]; then
  echo "AI_BAILIAN_API_KEY is required" >&2
  exit 2
fi

python3 - "$comparison_reports" <<'PY'
import json
import sys
import urllib.request
from pathlib import Path

reports = Path(sys.argv[1])
results = {}
for name, port in (("java", 18080), ("python", 28080)):
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/llm-provider/dashscope/test",
        data=b"",
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        results[name] = json.loads(response.read())

for value in results.values():
    data = value.get("data") or {}
    if value.get("code") != 200 or data.get("success") is not True:
        raise SystemExit(f"Real Provider smoke test failed: {value}")

if results["java"]["data"]["model"] != results["python"]["data"]["model"]:
    raise SystemExit("Java/Python real Provider model differs")

(reports / "real-model-smoke.json").write_text(
    json.dumps(results, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
PY

echo "Real model smoke test passed"

(
  cd "$repo_root/backend"
  uv run --frozen python ../migration/scripts/real_model_knowledge_base.py
)
