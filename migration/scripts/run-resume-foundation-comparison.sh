#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/comparison-common.sh"

seed="$repo_root/migration/samples/database/resume-foundation-seed.sql"
for service_and_db in \
  "java-postgres interview_guide_java" \
  "python-postgres interview_guide_python"
do
  read -r service database <<<"$service_and_db"
  compose exec -T "$service" \
    psql \
    --set ON_ERROR_STOP=1 \
    --username postgres \
    --dbname "$database" \
    <"$seed"
done

for bucket in interview-guide-java interview-guide-python
do
  python3 "$repo_root/migration/scripts/runtime_state.py" seed-s3 \
    --s3-endpoint http://127.0.0.1:19000 \
    --s3-access-key comparison-access \
    --s3-secret-key comparison-secret \
    --s3-bucket "$bucket" \
    --key resumes/2026/08/16/fixed_resume.txt \
    --content 'Fixed resume file bytes'
done

cases_file="$comparison_runtime/resume-foundation-cases.json"
cat >"$cases_file" <<'JSON'
{
  "cases": [
    {"id":"resume-list","method":"GET","path":"/api/resumes"},
    {"id":"resume-detail","method":"GET","path":"/api/resumes/2001/detail"},
    {"id":"resume-delete","method":"DELETE","path":"/api/resumes/2001"},
    {"id":"resume-deleted-detail","method":"GET","path":"/api/resumes/2001/detail"},
    {"id":"known-missing-statistics","method":"GET","path":"/api/resumes/statistics"}
  ],
  "trackedResponseHeaders":["content-type","vary"]
}
JSON

python3 "$repo_root/migration/scripts/comparison.py" capture-http \
  --url http://127.0.0.1:18080 \
  --cases "$cases_file" \
  --output "$comparison_reports/java-resume-foundation-http.json"
python3 "$repo_root/migration/scripts/comparison.py" capture-http \
  --url http://127.0.0.1:28080 \
  --cases "$cases_file" \
  --output "$comparison_reports/python-resume-foundation-http.json"

python3 "$repo_root/migration/scripts/comparison.py" compare \
  --left-http "$comparison_reports/java-resume-foundation-http.json" \
  --right-http "$comparison_reports/python-resume-foundation-http.json" \
  --left-schema "$repo_root/migration/samples/database/java-schema.sql" \
  --right-schema "$repo_root/migration/samples/database/java-schema.sql" \
  --json-report "$comparison_reports/resume-foundation-comparison.json" \
  --html-report "$comparison_reports/resume-foundation-comparison.html" \
  --title "Resume foundation Java/Python comparison"

python3 - "$repo_root" <<'PY'
import importlib.util
import sys
from pathlib import Path

root = Path(sys.argv[1])
module_path = root / "migration/scripts/runtime_state.py"
spec = importlib.util.spec_from_file_location("runtime_state", module_path)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Unable to load {module_path}")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
client = module.S3Client(
    "http://127.0.0.1:19000",
    "comparison-access",
    "comparison-secret",
    "us-east-1",
)
for bucket in ("interview-guide-java", "interview-guide-python"):
    if "resumes/2026/08/16/fixed_resume.txt" in client.list_objects(bucket):
        raise SystemExit(f"Resume object was not deleted from {bucket}")
PY

echo "Resume foundation comparison passed"
