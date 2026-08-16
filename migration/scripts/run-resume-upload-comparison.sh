#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/comparison-common.sh"

reset_sql='TRUNCATE TABLE interview_answers, interview_sessions, resume_analyses, resumes RESTART IDENTITY CASCADE;'
compose exec -T java-postgres \
  psql -v ON_ERROR_STOP=1 -U postgres -d interview_guide_java -c "$reset_sql"
compose exec -T python-postgres \
  psql -v ON_ERROR_STOP=1 -U postgres -d interview_guide_python -c "$reset_sql"
compose exec -T java-redis \
  redis-cli XTRIM resume:analyze:stream MAXLEN 0 >/dev/null || true
compose exec -T python-redis \
  redis-cli XTRIM resume:analyze:stream MAXLEN 0 >/dev/null || true

sample="$comparison_runtime/fixed-resume-upload.txt"
printf 'Fixed resume upload\nJava Python Redis' >"$sample"

curl --fail --silent --show-error \
  -X POST http://127.0.0.1:18080/api/resumes/upload \
  -F "file=@$sample;type=text/plain" \
  >"$comparison_reports/java-resume-upload.json"
curl --fail --silent --show-error \
  -X POST http://127.0.0.1:28080/api/resumes/upload \
  -F "file=@$sample;type=text/plain" \
  >"$comparison_reports/python-resume-upload.json"

python3 - "$comparison_reports" <<'PY'
import json
import sys
from pathlib import Path

reports = Path(sys.argv[1])
left = (reports / "java-resume-upload.json").read_text(encoding="utf-8")
right = (reports / "python-resume-upload.json").read_text(encoding="utf-8")
left = left.replace("interview-guide-java", "{{BUCKET}}")
right = right.replace("interview-guide-python", "{{BUCKET}}")
report = {
    "left": json.loads(left),
    "passed": json.loads(left) == json.loads(right),
    "right": json.loads(right),
}
(reports / "resume-upload-comparison.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
if not report["passed"]:
    raise SystemExit(1)
PY

echo "Resume first-upload comparison passed"
